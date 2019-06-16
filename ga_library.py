import json
import logging
import os
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import List, Callable, Union, Iterable, Optional, Any
from googleapiclient import discovery
from googleapiclient.http import build_http


try:
    from oauth2client import client
    from oauth2client import file
    from oauth2client import tools
except ImportError:
    raise ImportError('googleapiclient requires oauth2client. Please install oauth2client and try again.')

class GaProperty(Enum):
    XPlaneDotCom = 'UA-12381236-1'
    Mobile = 'UA-12381236-10'
    Desktop = 'UA-12381236-12'

    def __str__(self): return self.value

class CustomDimension(Enum):  # for desktop
    Aircraft = 2
    Region = 3
    Mission = 4
    EndCondition = 5
    Retry = 7
    ProductLevel = 8
    Screen = 10
    VrHeadset = 11
    VrControllers = 12
    FlightControls = 13
    RenderingSettings = 14
    AcfStartType = 15
    Os = 16
    Cpu = 17
    Gpu = 18
    Ram = 19
    AbTests = 20

    def __str__(self): return "ga:dimension%d" % self.value

class Metric(Enum):
    Events = 'ga:totalEvents'
    Users = 'ga:users'
    Sessions = 'ga:sessions'
    Crashes = 'ga:fatalExceptions'

    def __str__(self): return self.value

class UserGroup(Enum):
    All = ''
    PaidOnly = 'ga:dimension8!@Demo'  # filter out people with product levels that include "Demo" as a substring (i.e., show us only paying users)
    DemoOnly = 'ga:dimension8=@Demo'

    def __str__(self): return self.value

@dataclass
class VersionMetadata:
    name: str
    is_final: bool  # True if this is a "stable"/final release; false if it's a beta or a pre-final release candidate/RC
    start: str
    end: str = 'today'

    @property
    def start_date(self):
        return date.fromisoformat(self.start)

    @property
    def end_date(self):
        if self.end == 'today':
            return date.today()
        return date.fromisoformat(self.end)

    @property
    def is_specific_release(self):
        return len(self.name) > 2

    def has_full_data_retention(self):
        end_of_retention = date.today()
        for i in range(26):
            end_of_retention = end_of_retention.replace(day=1) - timedelta(days=1)
        return self.start_date > end_of_retention


class Version(Enum):
    v10     = VersionMetadata(name='10',      is_final=False, start='2015-09-19', end='2017-06-01')  # Sep 2015 is when 10.40 went final and we started getting data from more than just hardcore early adopters; 2016 date is a half year after 11.00pb1
    v1051r2 = VersionMetadata(name='10.51r2', is_final=True,  start='2016-10-26', end='2017-06-01')
    v11     = VersionMetadata(name='11',      is_final=False, start='2016-11-24', end='today')  # Date when 11.00pb1 went live
    v1120r4 = VersionMetadata(name='11.20r4', is_final=True,  start='2018-05-02', end='2019-01-22')
    v1126r2 = VersionMetadata(name='11.26r2', is_final=True,  start='2018-08-23', end='2019-01-22')
    v1130r1 = VersionMetadata(name='11.30r1', is_final=False, start='2018-12-14', end='2018-12-25')
    v1130r2 = VersionMetadata(name='11.30r2', is_final=False, start='2018-12-24', end='2019-01-10')
    v1130r3 = VersionMetadata(name='11.30r3', is_final=True,  start='2019-01-08', end='2019-02-02')
    v1131r1 = VersionMetadata(name='11.31r1', is_final=True,  start='2019-01-26', end='2019-03-11')
    v1132r1 = VersionMetadata(name='11.32r1', is_final=False, start='2019-02-06', end='2019-02-22')
    v1132r2 = VersionMetadata(name='11.32r2', is_final=True,  start='2019-02-21', end='2019-05-01')
    v1133b1 = VersionMetadata(name='11.33b1', is_final=False, start='2019-02-21', end='2019-05-07')
    v1133r1 = VersionMetadata(name='11.33r1', is_final=False, start='2019-04-24', end='2019-08-01')
    v1133r2 = VersionMetadata(name='11.33r2', is_final=True,  start='2019-04-26', end='today')
    v1134r1 = VersionMetadata(name='11.34r1', is_final=True,  start='2019-05-07', end='today')
    v1135b2 = VersionMetadata(name='11.35b2', is_final=False, start='2019-06-06', end='today')

    def __str__(self): return self.value.name


class Cache(Enum):
    OnDisk = 1
    InMemory = 2

def cached(cache_type: Cache=Cache.InMemory, expiration_minutes: float=24 * 60):
    def wrapper_wrapper_sigh(func: Callable):  # This is what it takes to pass a parameter to your decorator... https://stackoverflow.com/a/10176276/1417451
        def wrapper_factory(cached: Callable, read_from_cache: Callable, write_to_cache: Callable):
            def serialize_args(*args, **kwargs):
                def is_just_an_object(arg: str): return all(token in arg for token in ('<', '>', ' object at '))

                return '_'.join([str(arg) for arg in args if not is_just_an_object(str(arg))] +
                                ["%s-%s" % (k, v) for k, v in kwargs])

            def wrapper(*args, **kwargs):
                cache_id = func.__name__ + '-' + serialize_args(*args, **kwargs)
                if cached(cache_id):
                    return read_from_cache(cache_id)
                else:
                    out = func(*args, **kwargs)
                    write_to_cache(cache_id, out)
                    assert out == read_from_cache(cache_id), 'Serialization failed'
                    return out
            return wrapper

        def expired(modification_time: float):
            mins_since_modification = (time.time() - modification_time) / 60
            return mins_since_modification > expiration_minutes

        if cache_type == Cache.InMemory:
            cache = {}  # in-memory cache of IDs associated with a tuple of (modification time, data)
            def write_to_cache(cache_id: str, value: Any):
                cache[cache_id] = (time.time(), json.dumps(value))

            return wrapper_factory(cached=lambda cache_id: cache_id in cache and not expired(cache[cache_id][0]),
                                   read_from_cache=lambda cache_id: json.loads(cache[cache_id][1]),
                                   write_to_cache=write_to_cache)
        else:
            cache_dir = Path(__file__).parent / '.ga_cache/'
            cache_dir.mkdir(exist_ok=True)

            def cached(cache_id: str):
                cache_path = cache_dir / cache_id
                return cache_path.exists() and not expired(cache_path.stat().st_mtime)

            def read_from_cache(cache_id: str):
                with (cache_dir / cache_id).open() as in_file:
                    return json.loads(in_file.read())

            def write_to_cache(cache_id: str, value: Any):
                with (cache_dir / cache_id).open('w') as out_file:
                    out_file.write(json.dumps(value))

            return wrapper_factory(cached, read_from_cache, write_to_cache)
    return wrapper_wrapper_sigh

def disk_cached(func: Callable, expiration_minutes: float=24 * 60):
    return cached(func, Cache.OnDisk, expiration_minutes)

def mem_cached(func: Callable, expiration_minutes: float=24 * 60):
    return cached(func, Cache.InMemory, expiration_minutes)


class GaService:
    account_id = '12381236'  # X-Plane's GA account ID

    @staticmethod
    def desktop():
        return GaService(GaProperty.Desktop)

    def __init__(self, property):
        """
        :param property: The Google Analytics property you want to operate on
        :type property: GaProperty
        :param scope: The OAuth scope used
        :type scope: str|None
        """
        self.property = str(property)

        credentials_json = os.getenv('GA_CREDENTIALS')
        assert credentials_json, 'GA_CREDENTIALS environment variable must be set to the contents of analytics.dat'
        credentials = client.Credentials.new_from_json(credentials_json)
        http = credentials.authorize(http=build_http())
        self.service = discovery.build('analytics', 'v3', http=http)
        assert self.service, 'Failed to set up analytics service'
        """:type self.service: googleapiclient.discovery.Resource"""

        profiles = self.service.management().profiles().list(
            accountId=self.account_id,
            webPropertyId=self.property).execute()
        self.profile_id = profiles.get('items')[0].get('id')
        assert isinstance(self.profile_id, str) and self.profile_id, 'Failed to set up analytics connection'

    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, self.property)


    @cached(cache_type=Cache.OnDisk if os.getenv('GA_CACHE_DISK') else Cache.InMemory)
    def query(self, app_version: Union[Version, int], metric: Metric, dimensions: Union[str, Iterable[str], CustomDimension, Iterable[CustomDimension], None]=None, additional_filters: Union[str, UserGroup, None]=None, override_start_date: Optional[Union[date, str]]=None, strict_mode: bool=False) -> List[List[str]]:
        """
        :param strict_mode: If true, we won't return any results at all for incomplete queries; otherwise, we'll return as much data as we have.
        :return: The rows of results
        """
        if isinstance(app_version, int):
            for v in Version:
                with suppress(ValueError):
                    if app_version == int(v.value.name):
                        app_version = v
                        break
            else:  # nobreak
                raise ValueError('app_version must be convertable to a Version enum')

        if strict_mode and metric == Metric.Users and not app_version.value.has_full_data_retention():
            logging.warning("Refusing to answer users query for version %s (metric %s) with incomplete data retention" % (app_version, metric))
            return []

        version_filter = "ga:appVersion=@X-Plane " + str(app_version)
        if isinstance(dimensions, list):
            dimension_str = ';'.join(str(d) for d in dimensions)
        else:
            dimension_str = str(dimensions) if dimensions else ''

        results = self.service.data().ga().get(
            ids='ga:' + self.profile_id,
            samplingLevel="HIGHER_PRECISION",
            start_date=str(override_start_date) if override_start_date else app_version.value.start,
            end_date=app_version.value.end,
            metrics=metric.value,
            dimensions=dimension_str,
            sort="-" + metric.value,
            filters=version_filter + (';' + str(additional_filters) if additional_filters else ''),
        ).execute()
        out = results.get('rows')
        if out:
            return out
        else:
            logging.warning("No results for metric %s, version %s (this almost certainly indicates a logic error)" % (metric, app_version))
            return []

    def users(self, app_version, dimensions=None, additional_filters=None):
        return self.query(app_version, Metric.Users, dimensions, additional_filters)

    def sessions(self, app_version, dimensions=None, additional_filters=None):
        return self.query(app_version, Metric.Sessions, dimensions, additional_filters)

    def events(self, app_version, dimensions=None, additional_filters=None, override_start_date=None):
        return self.query(app_version, Metric.Events, dimensions, additional_filters, override_start_date)

    def crashes(self, app_version, dimensions=None, additional_filters=None):
        return self.query(app_version, Metric.Crashes, dimensions, additional_filters)


class VersionQueryMgr:
    def __init__(self, service: GaService, version: Version):
        self.service = service
        self.version = version

    def __str__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self.service.property, str(self.version))

    def query(self, metric, dimensions=None, additional_filters=None, override_start_date: Optional[Union[date, str]]=None) -> List[List[str]]:
        return self.service.query(self.version, metric, dimensions, additional_filters, override_start_date)

    def users(self, dimensions=None, additional_filters=None):
        return self.query(Metric.Users, dimensions, additional_filters)

    def sessions(self, dimensions=None, additional_filters=None):
        return self.query(Metric.Sessions, dimensions, additional_filters)

    def events(self, dimensions=None, additional_filters=None):
        return self.query(Metric.Events, dimensions, additional_filters)

    def crashes(self, dimensions=None, additional_filters=None):
        return self.query(Metric.Crashes, dimensions, additional_filters)

    def total_users(self):
        user_rows = self.users()
        return int(user_rows[0][0]) if user_rows else None
    def total_sessions(self): return int(self.sessions()[0][0])
    def total_events(self):   return int(self.events()[0][0])
    def total_crashes(self):  return int(self.crashes()[0][0])



class SimpleQueryMgr:
    def __init__(self, service, version, metric, filters):
        """
        :type service: GaService
        :type version: Version
        :type metric: Metric
        :type filters: str|None|UserGroup
        """
        self.version_qm = VersionQueryMgr(service, version)
        self.metric = metric
        self.filters = filters


    def __str__(self):
        return "%s(%s, %s, %s, %s)" % (self.__class__.__name__, self.version_qm.service.property, str(self.version_qm.version), str(self.metric), str(self.filters))

    def query(self, dimension: CustomDimension, override_start_date: Optional[Union[date, str]]=None) -> List[List[str]]:
        return self.version_qm.query(self.metric, dimension, self.filters, override_start_date)
