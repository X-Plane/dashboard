#!/usr/bin/env python3
import collections
import os
import typing
from datetime import datetime
from enum import Enum
from typing import Optional
import requests

from ga_library import cached, Cache
from utils import make_absolute_bar_chart_figure


class GatewayStat(Enum):
    Airports = 'airports'
    Airports3D = 'recommended3dAirports'
    Submissions = 'totalUserSceneryPacks'
    Artists = 'registeredArtists'


class GatewayStatsReporter:
    stats_url = 'http://gateway.x-plane.com/apiv1/stats/by-month'

    def stat_over_time(self, stat: GatewayStat):
        return self._time_series_count(stat.value)

    def _time_series_count(self, key: str) -> typing.OrderedDict[str, int]:
        out = collections.OrderedDict()
        all_by_month = self._all_stats_by_month()
        assert key in all_by_month, f'Unknown key: {key}'
        current_date = datetime.now()
        for month, count in zip(all_by_month['months'], all_by_month[key]):
            if datetime.strptime(month, '%Y-%m') < current_date:
                out[month] = count
        return out

    @cached(cache_type=Cache.OnDisk if os.getenv('GA_CACHE_DISK') else Cache.InMemory)
    def _all_stats_by_month(self):
        # Sample data:
        # {"months":["2015-01","2015-02","2015-03","2015-04","2015-05","2015-06","2015-07","2015-08","2015-09","2015-10","2015-11","2015-12","2016-01","2016-02","2016-03","2016-04","2016-05","2016-06","2016-07","2016-08","2016-09","2016-10","2016-11","2016-12","2017-01","2017-02","2017-03","2017-04","2017-05","2017-06","2017-07","2017-08","2017-09","2017-10","2017-11","2017-12","2018-01","2018-02","2018-03","2018-04","2018-05","2018-06","2018-07","2018-08","2018-09","2018-10","2018-11","2018-12","2019-01","2019-02","2019-03","2019-04","2019-05","2019-06","2019-07","2019-08","2019-09","2019-10","2019-11","2019-12"],
        #  "airports":[1411,32167,32267,32330,34434,34514,34553,34593,34620,34635,34661,34683,34695,34784,34813,34829,34833,34850,34862,34871,34889,34952,34971,34991,35002,35021,35031,35051,35074,35093,35107,35142,35179,35240,35295,35360,35396,35467,35509,35593,35640,35640,35640,35643,35644,35644,35644,35644,35644,35644,35644,35644,35644,35644,35644,35644,35645,35645,35645,35645],
        #  "recommended3dAirports":[431,499,620,770,849,946,1021,1098,1204,1286,1395,1469,1540,1680,1775,1838,1896,1944,2035,2088,2149,2229,2336,2521,2633,2780,3210,3311,3446,3620,3780,4142,4401,4721,4930,5142,5495,5949,6292,6782,7048,7048,7048,7051,7052,7052,7052,7052,7052,7052,7052,7052,7052,7052,7052,7052,7053,7053,7053,7053],
        #  "totalUserSceneryPacks":[1242,1473,1857,2202,2591,2833,3081,3871,4043,4315,4543,4838,5112,5368,5537,5706,5898,6128,6424,6698,6904,7119,7641,7951,8344,8682,8926,9194,9563,10145,10621,11121,11668,12205,12762,13311,14039,14948,15534,16268,16630,16630,16750,16784,16889,16889,16889,16907,16909,16909,16909,16909,16909,16911,16911,16963,16968,16996,16996,16996],
        #  "registeredArtists":[323,392,470,544,604,644,697,753,822,893,951,1036,1146,1240,1326,1416,1496,1596,1705,1808,1899,1988,2087,2169,2298,2434,2557,2656,2848,3047,3217,3406,3631,3782,3944,4091,4276,4453,4601,4797,4939,4941,4949,4964,4974,4974,4976,4978,4978,4978,4978,4978,4978,4979,4979,5020,5020,5052,5052,5052]}
        all_stats_by_month = requests.get(self.stats_url).json()
        assert all(stat.value in all_stats_by_month for stat in GatewayStat), 'Missing required metric from the server'
        assert all(len(all_stats_by_month[stat.value]) == len(all_stats_by_month['months'])
                   for stat in GatewayStat), 'Missing required metric from the server'
        return all_stats_by_month


class GatewayGrapher:
    def __init__(self):
        self.stats = GatewayStatsReporter()

    def airports_over_time(self, with_title=False, color: Optional[str]=None):
        return make_absolute_bar_chart_figure(self.stats.stat_over_time(GatewayStat.Airports), '', y_label='Number of Airports (2-D or 3-D)',
                                              title='Airports with 2-D or 3-D Scenery' if with_title else None, bar_color=color)

    def airports_3d_over_time(self, with_title=False, color: Optional[str]=None):
        return make_absolute_bar_chart_figure(self.stats.stat_over_time(GatewayStat.Airports3D), '', y_label='Number of 3-D Airports',
                                              title='Airports with 3-D Scenery' if with_title else None, bar_color=color)

    def total_submissions_over_time(self, with_title=False, color: Optional[str]=None):
        return make_absolute_bar_chart_figure(self.stats.stat_over_time(GatewayStat.Submissions), '', y_label='Number of Scenery Submissions',
                                              title='Total Scenery Pack Submissions' if with_title else None, bar_color=color)

    def registered_artists_over_time(self, with_title=False, color: Optional[str]=None):
        return make_absolute_bar_chart_figure(self.stats.stat_over_time(GatewayStat.Artists), '', y_label='Number of Artists',
                                              title='Registered Scenery Artists' if with_title else None, bar_color=color)
