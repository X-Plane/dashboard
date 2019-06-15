#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Accesses the Google Analytics API to spit out a CSV of aircraft usage"""

from __future__ import division, print_function
import argparse
import collections
import xlsxwriter
from datetime import datetime
from ga_library import *
from utils import *


SHOW_ABSOLUTE_NUMBERS = False
file_name_suffix = ''


class Category(Enum):
    GenAv = 'General Aviation'
    Airliner = 'Airliner'
    Cargo = 'Cargo'
    Seaplane = 'Seaplane'
    Heli = 'Helicopter'
    Glider = 'Glider'
    Military = 'Military'
    Experimental = 'Experimental'
    Ultralight = 'Ultralight'
    Vtol = 'VTOL'
    SciFi = 'Science Fiction'

    def __str__(self):
        return self.value

    @staticmethod
    def from_string(category_str):
        """
        :type category_str: str
        :rtype: Category
        """
        category_str = str(category_str.strip())
        mappings = {
            Category.GenAv: [u'Aviação Geral', u'小型機', u'Avion général', u'Малая авиация', u'Aviation Générale', u'Aviación General', u'Avión de Pasajeros', 'Aviazione Generale', 'Allgemeine Luftfahrt', 'Avion de tourisme'],
            Category.Airliner: ['Aereo di linea', 'Verkehrsflugzeug', 'Avion de ligne', 'Avion de Ligne', u'Aviação Comercial', u'Авиалайнеры', u'航空会社', u'民航客机', u'客机', u'通用航空器'],
            Category.Seaplane: ['Hydravion', 'Flugboot', u'Hidroavión', u'水上飛行機', 'Idrovolante', '水上飞机'],
            Category.Heli: ['Hubschrauber', 'Elicottero', u'Helicóptero', u'Hélicopter', u'Hélicoptère', u'Вертолеты', u'ヘリコプター', '直升机'],
            Category.Glider: ['Segler', 'Planador', u'Планёры', 'Planeador', 'Planeur', 'Segelflieger', 'Aliante', u'グライダー', '滑翔机'],
            Category.Military: [u'Militär', 'Militaire', 'Militar', 'Militare', u'軍用機', '军用飞机', 'Военные ЛА'],
            Category.Experimental: [u'Expérimental', 'Sperimentale', u'実験機', '试验机'],
            Category.Ultralight: ['Ultra', 'Ultraleicht', 'Ultraligero', u'超軽量飛行機', u'Ultra-Léger', u'Ultraleggero', '超轻型飞机', 'Сверхлегкие'],
            Category.SciFi: [u'サイエンスフィクション'],
            Category.Vtol: [u'Cамолёты вертикального взлёта и посадки'],
            Category.Cargo: ['Fracht', 'Cargamento']
        }
        for cat, translations in mappings.items():
            if category_str in translations:
                return cat

        match = [e for e in Category if e.value == category_str]
        assert match, "No known category \"%s\"" % category_str
        return match[0]


class Aircraft(object):
    lr_studio = 'Laminar Research'
    
    def __init__(self, name, categories, engines, studio=None):
        """
        :type name: str
        :param categories: Category|collections.Iterable[Category]
        :param engines: int
        :param studio: str|None
        """
        if isinstance(categories, Category):
            categories = set([categories])
        assert isinstance(name, str)
        assert isinstance(categories, collections.Iterable)
        assert all(isinstance(c, Category) for c in categories)
        assert isinstance(engines, int)
        assert isinstance(studio, str) or not studio
        self.name = name.strip()
        self.categories = set(categories)
        self.engines = engines
        self.studio = studio.strip() if studio else 'Other'

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.name == other.name and self.categories == other.categories and self.studio == other.studio and self.engines == other.engines

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.name, len(self.categories), self.engines, self.studio))

    def __str__(self):
        if self.studio:
            return "%s (%s)" % (self.name, self.studio)
        else:
            return self.name

    def is_first_party(self):
        first_party_planes = [
            Aircraft(studio=Aircraft.lr_studio, name='Cessna 172SP',             categories=[Category.GenAv],        engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='Baron B58',                categories=[Category.GenAv],        engines=2),
            Aircraft(studio=Aircraft.lr_studio, name='B747-400 United',          categories=[Category.Airliner],     engines=4),
            Aircraft(studio=Aircraft.lr_studio, name='Cirrus TheJet',            categories=[Category.GenAv],        engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='KingAir C90B',             categories=[Category.GenAv],        engines=2),
            Aircraft(studio=Aircraft.lr_studio, name='B777-200 British Airways', categories=[Category.Airliner],     engines=2),
            Aircraft(studio=Aircraft.lr_studio, name='Bell 206',                 categories=[Category.Heli],         engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='FA-22 Raptor',             categories=[Category.Military],     engines=2),
            Aircraft(studio=Aircraft.lr_studio, name='RV-10',                    categories=[Category.Experimental], engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='P180 Avanti Ferrari Team', categories=[Category.GenAv],        engines=2),
            Aircraft(studio=Aircraft.lr_studio, name='X-15',                     categories=[Category.Experimental], engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='StinsonL5',                categories=[Category.GenAv],        engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='Columbia-400',             categories=[Category.GenAv],        engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='Robinson R22 Beta',        categories=[Category.Heli],         engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='KC-10',                    categories=[Category.Airliner],     engines=3),
            Aircraft(studio=Aircraft.lr_studio, name='B747-100 NASA',            categories=[Category.Airliner],     engines=4),
            Aircraft(studio=Aircraft.lr_studio, name='F-4 Phantom',              categories=[Category.Military],     engines=2),
            Aircraft(studio=Aircraft.lr_studio, name='ASK21',                    categories=[Category.Glider],       engines=0),
            Aircraft(studio=Aircraft.lr_studio, name='C-130',                    categories=[Category.Airliner],     engines=4),
            Aircraft(studio=Aircraft.lr_studio, name='Space Shuttle',            categories=[Category.Experimental], engines=3),
            Aircraft(studio=Aircraft.lr_studio, name='Marines Sea Harrier',      categories=[Category.Vtol],         engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='Viggen JA37',              categories=[Category.Military],     engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='Lancair Evolution',        categories=[Category.Experimental], engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='SR-71 Blackbird-D21a',     categories=[Category.Military],     engines=2),
            Aircraft(studio=Aircraft.lr_studio, name='Northrop B-2 Spirit',      categories=[Category.Military],     engines=4),
            Aircraft(studio=Aircraft.lr_studio, name='Japanese Anime',           categories=[Category.SciFi],        engines=2),
            Aircraft(studio=Aircraft.lr_studio, name='X-30 NASP',                categories=[Category.Experimental], engines=6),
            Aircraft(studio=Aircraft.lr_studio, name='B-52G NASA',               categories=[Category.Military],     engines=8),
            Aircraft(studio=Aircraft.lr_studio, name='Rockwell B-1B Lancer',     categories=[Category.Military],     engines=4),
            Aircraft(studio=Aircraft.lr_studio, name='GP_PT_60',                 categories=[Category.Experimental], engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='X-1 Cavallo',              categories=[Category.Experimental], engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='Experimental',             categories=[Category.Experimental], engines=8),
            Aircraft(studio=Aircraft.lr_studio, name='Experimental',             categories=[Category.Experimental], engines=1),
            Aircraft(studio=Aircraft.lr_studio, name='Experimental',             categories=[Category.Experimental], engines=2),
        ]
        return self.studio == Aircraft.lr_studio or self in first_party_planes

    @staticmethod
    def from_str(acf_string):
        """
        :type acf_string: str
        :rtype: Aircraft
        """
        classifications = set()
        studio = None
        engines = None
        remaining = str(acf_string)
        splitters = [" - %s: " % s for s in ('Class', 'Studio', 'Engines')]  # in the order in which they appear in acf_string
        if splitters[-1] in remaining:
            remaining, engines_str = remaining.split(splitters[-1])
            engines = int(engines_str)
        if splitters[-2] in remaining:
            remaining, studio = remaining.split(splitters[-2])
        if splitters[-3] in remaining:
            remaining, classes = remaining.split(splitters[-3])
            classifications = set(Category.from_string(c) for c in classes.split("/"))
        name = remaining

        if engines is None:
            if 'Twin Beech' in name:
                engines = 2
            elif 'Turbo 310R' in name:
                engines = 1
        if studio and studio.strip() == 'JARDESIGN (C)':
            studio = 'JARDesign'
        elif studio.endswith('dmax3d.com'):
            studio = 'dmax3d.com'
        elif 'Just Flight' in studio:
            studio = studio.replace('Just Flight', 'JustFlight')
        elif '_JARDesign' in name:
            name = name.replace('_JARDesign', '')
            studio = 'JARDesign'

        if not studio or studio == 'Other':
            if name.strip() in ['Bell 206', 'Baron B58', 'B747-400 United', 'FA-22 Raptor', 'B777-200 British Airways', 'KingAir C90B', 'Cirrus TheJet', 'F-4 Phantom', 'C-130', 'Robinson R22 Beta', 'P180 Avanti Ferrari Team', 'ASK21', 'X-15', 'SR-71 Blackbird-D21a', 'Lancair Evolution', 'B747-100 NASA', 'StinsonL5', 'KC-10', 'Viggen JA37', 'Marines Sea Harrier', 'B-52G NASA', 'Japanese Anime', 'Northrop B-2 Spirit', 'X-30 NASP']:
                studio = Aircraft.lr_studio
            elif '320 neo' in name.lower() or '320neo' in name.lower() or '321neo' in name.lower():
                name = 'A320'
                studio = 'JARDesign'
            elif '330 neo' in name.lower():
                name = 'A330'
                studio = 'JARDesign'
            elif 'Boeing737-800_x737' in name:
                name = 'Boeing 737-800'
                studio = 'x737 project, EADT'
            elif 'FlightFactor ' in name:
                name = name.replace('FlightFactor ', '')
                studio = 'Flight Factor'
            elif 'Flight Factor ' in name:
                name = name.replace('Flight Factor ', '')
                studio = 'Flight Factor'
            elif 'Boeing 757' in name:
                studio = 'Flight Factor and StepToSky'
            elif name.startswith('IXEG '):
                name = name.replace('IXEG ', '')
                studio = 'IXEG'
            elif 'Piper' and 'Arrow' in name:
                name = 'PA28 Arrow'
                studio = 'JustFlight/Thranda Design'
            elif 'CRJ-200' in name:
                name = 'Bombardier CRJ-200'
                studio = 'JRollon'
            elif 'Bell 429' in name:
                name = 'Bell 429'
                studio = 'timber61'
            elif 'Let L-410' in name:
                studio = 'X-Plane.hu'
            elif 'H145' in name:
                studio = 'Liebernickel'
                name = 'H145'
            elif 'MBB Kawasaki BK-117B2' in name:
                name = 'MBB Kawasaki BK-117B2'
                studio = 'ND Art & Technology'
            elif 'Boeing 787-9' in name:
                studio = 'Magknight'
                classifications = set([Category.Airliner])
            elif 'Lancair Legacy' in name:
                studio = 'nicolas'
            elif 'Ikarus C42' in name:
                studio = 'vFlyteAir'
            elif 'Dash 7-150' in name:
                studio = 'Stingray14'

        if name.startswith('Boeing 757-200'):
            name = 'Boeing 757-200'
        elif studio == 'IXEG' and '737' in name:
            name = 'Boeing 737-300'
        elif 'A380-plus' in name:
            name = 'A380-plus'
            studio = 'riviere'
            classifications = set([Category.Airliner])

        if studio:
            if studio == 'x737 project, EADT' and name == 'B738':
                name = 'Boeing 737-800'
            elif studio == 'EADT' and '737-700' in name:
                name = 'Boeing 737-700'
                studio = 'x737 project, EADT'
            elif studio.startswith('Airfoillab'):
                studio = 'Airfoillabs'
            elif studio.lower() == 'jardesign':
                studio = 'JARDesign'
                if '320' in name:
                    name = 'A320'
                    classifications = set([Category.Airliner])
                if '321' in name:
                    name = 'A321'
                    classifications = set([Category.Airliner])
                elif '330' in name:
                    name = 'A330'
                    classifications = set([Category.Airliner])
            elif 'FlightFactor' in studio:
                studio = studio.replace('FlightFactor', 'Flight Factor')
            elif studio == 'Rotate' and 'MD-80' in name:
                name = 'MD-80'
            elif studio == 'ToLiss' and 'A319' in name:
                name = 'Airbus A319'
            elif studio == 'ghansen' and 'Gulfstream' in name:
                classifications = set([Category.Airliner])
            elif studio == 'FlyJSim':
                if '727' in name:
                    name = 'Boeing 727'
                elif '732 Twinjet' in name:
                    name = 'Boeing 737-200'
            elif studio == 'XPFR' and 'RAFALE C' in name:
                name = 'Rafale C'
            elif studio == 'Aerobask':
                if 'Epic E1000' in name:
                    name = 'Epic E1000'
            elif studio == Aircraft.lr_studio:
                if "Avanti" in name:
                    name = 'Piaggio P.180 Avanti'
                elif 'Baron' in name:
                    name = 'Baron B58'
                elif 'Cirrus' in name:
                    name = 'Cirrus Vision SF50'
                elif '747-100' in name:
                    name = 'Boeing 747-100'
                elif 'Stinson' in name:
                    name = 'Stinson L-5 Sentinel'
                elif 'F-22' in name or 'FA-22' in name:
                    name = 'FA-22 Raptor'
                elif '747-400' in name:
                    name = 'Boeing 747-400'
                elif 'Harrier' in name:
                    name = 'AV-8B Harrier II'
                    classifications = set([Category.Vtol, Category.Military])
                elif 'Bell 206' in name:
                    name = 'Bell 206'
                elif 'King' in name and 'Air' in name:
                    name = 'King Air C90'
                elif '172' in name:
                    name = 'Cessna Skyhawk'
                elif 'F-4' in name:
                    name = 'F-4 Phantom II'
                elif 'MD-82' in name:
                    name = 'MD-82'
                    classifications = set([Category.Airliner])
                elif 'Viggen' in name:
                    name = 'JA 37 Viggen'
                elif 'ASK' in name and '21' in name:
                    name = 'Schleicher ASK 21'
                elif 'B-52' in name:
                    name = 'B-52G Stratofortress'

                if 'Boeing' in name:
                    classifications = set([Category.Airliner])

        if 'Boeing757v' in name:
            name = 'Boeing 757'
            if not studio:
                studio = 'FlightFactor and StepToSky'
        elif 'CRJ-200' in name:
            name = 'Bombardier CRJ-200'
            classifications = set([Category.Airliner])
        elif 'Tecnam' in name and 'P2002' in name:
            name = 'Tecnam P2002'
            classifications = set([Category.GenAv, Category.Ultralight])
        elif 'Antares 20E' in name:
            classifications = set([Category.Glider])
        elif 'Epic_E1000_Skyview' in name:
            name = 'Epic E1000 Skyview'
        elif 'Akoya' in name:
            name = 'Lisa Akoya'
        elif name in ('B200 King Air', 'Cessna T210M Centurion II', 'C90 King Air', 'Piper PA-31 Navajo', 'F33A Bonanza') and studio == 'Carenado':
            studio = 'Carenado/Thranda Design'
        elif 'V35' in name and 'Bonanza' in name and 'Carenado' in studio:
            name = 'Bonanza V35B'
        elif 'B58 Baron' in name and 'Carenado' in studio:
            name = 'Beechcraft B58 Baron'
            studio = 'Carenado/Thranda Design'
        elif 'Cessna T210M Centurion II' in name and 'Carenado' in studio:
            name = 'Cessna T210M Centurion II'
            studio = 'Carenado/Thranda Design'
        elif 'x737-800' in name:
            name = 'Boeing 737-800'
            studio = 'x737 project, EADT'
        elif '320 ultimate' in name.lower() or '320ultimate' in name.lower() or name == 'FF_A320' or 'FlightFactorA320' in name or name == 'A320FF' or name == 'FF A320' or name == 'FFA320':
            name = 'A320 Ultimate'
            studio = 'Flight Factor'
        elif 'Boeing 737-800X' in name and 'Zibo' in studio:
            studio = u'Laminar Research modify by Zibo and Twkster'

        for to_nuke in [' for X-Plane 11', 'Aerobask ', 'X-Crafts ', ' XP11', 'Carenado ', ' for XP11', ' For XP11', 'FJS ', 'Airfoillabs ']:
            name = name.replace(to_nuke, '')
        name = name.strip()

        if not studio or studio == 'Other':
            if ('boeing777' in name.lower() and 'extended' in name.lower()) or name == '777 Worldliner Professional':
                studio = 'Flight Factor'
                name = 'Boeing 777'
            if name == 'Boeing 757' or name.startswith('Boeing757-200v'):
                studio = 'Flight Factor and StepToSky'

        if 'Flight Factor' in studio:
            if '777' in name:
                name = 'Boeing 777'
            elif 'a350' in name.lower():
                name = 'Airbus A350'
            elif 'a320' in name.lower():
                name = 'A320 Ultimate'
                studio = 'Flight Factor'
            elif 'boeing777' in name.lower():
                name = 'Boeing 777'
            elif name.startswith('Boeing 767'):
                name = 'Boeing 767'
            elif name.startswith(('Boeing 757', 'Boeing757', 'FlightFactor Boeing 757')):
                name = 'Boeing 757'

        if engines is None:
            if name.startswith(('F-35A', 'T-6B', 'T-6A', 'MB339A')):
                engines = 1
            elif name.startswith('Beech D18S'):
                engines = 2

        if name.startswith(('Boeing 737', 'Boeing 747', 'Boeing 757', 'Boeing 767', 'Airbus A32', 'Airbus A31', 'Airbus A33', 'Airbus A34', 'Airbus A35', 'A320 ')):
            classifications = set([Category.Airliner])

        return Aircraft(name, classifications, engines, studio)


class AnalysisWriter(object):
    def __init__(self, out_name):
        now = datetime.now()
        self.workbook = xlsxwriter.Workbook("%s - %04d-%02d.xlsx" % (out_name, now.year, now.month))
        self.worksheet = self.workbook.add_worksheet()
        self.row_idx = 0
        self.bold_format = self.workbook.add_format({'bold': True})
        self.percent_format = self.workbook.add_format({'num_format': '#.00%'})
        self.worksheet.set_column(0, 0, 30)  # 30 units wide, text format
        self.worksheet.set_column(1, 1, 7)
        self.worksheet.set_column(2, 2, 20)
        self.worksheet.set_column(3, 3, 20)
        self.worksheet.set_column(4, 4, 10, self.percent_format)

    def dump_dict(self, heading, dictionary, total_flights):
        self.output_row([heading], self.bold_format)
        self.output_row(self.get_headings(dictionary), self.bold_format)

        sorted_dict = sorted(dictionary.items(), key=operator.itemgetter(1), reverse=True)
        for i, item_and_count in enumerate(sorted_dict):
            self.output_row(self.get_row_data(item_and_count[0], item_and_count[1], total_flights))
        self.row_idx += 1

    def output_row(self, columns, format=None):
        for col_idx, item in enumerate(columns):
            self.worksheet.write(self.row_idx, col_idx, item, format)
        self.row_idx += 1

    def get_headings(self, dictionary):
        if dictionary:
            first_item = next(iter(dictionary))
            if isinstance(first_item, Aircraft):
                headings = ['Aircraft', 'Engines', 'Classification', 'Studio']
            elif isinstance(first_item, Category):
                headings = ['Category', '', '', '']
            else:
                raise TypeError('Unknown type for ' + first_item)
            headings.append('% Flights')
            return headings
        return []

    def get_row_data(self, item, count, total):
        if isinstance(item, Aircraft):
            cols = [item.name, item.engines, ', '.join(str(c) for c in item.categories), item.studio]
        elif isinstance(item, Category):
            cols = [str(item), '', '', '']
        else:
            raise TypeError('Unknown type for ' + item)
        cols.append(count / total)
        return cols


if SHOW_ABSOLUTE_NUMBERS:
    class AbsoluteNumbersAnalysisWriter(AnalysisWriter):
        def get_headings(self, first_col_heading):
            out = super(AbsoluteNumbersAnalysisWriter, self).get_headings(first_col_heading)
            out.append('Num Flights')
            return out

        def get_row_data(self, item, count, total):
            out = super(AbsoluteNumbersAnalysisWriter, self).get_row_data(item, count, total)
            out.append(count)
            return out


@dataclass
class AircraftStats:
    first_party: Dict[Aircraft, int]
    third_party: Dict[Aircraft, int]
    combined: Dict[Aircraft, int]

    @property
    def categories(self) -> Dict[str, int]:
        categories = collections.defaultdict(int)
        for acf, count in self.combined.items():
            for classification in acf.categories:
                categories[classification] += count
        return categories

    @property
    def total_flights(self):
        return sum(count for count in self.combined.values())

    @property
    def first_party_flights(self):
        return sum(count for count in self.first_party.values())

    @property
    def third_party_flights(self):
        return sum(count for count in self.third_party.values())

    @staticmethod
    def from_ga(service: GaService, version: Version, user_group: UserGroup):
        results_rows = service.events(version, CustomDimension.Aircraft, user_group)

        first_party_rankings = collections.defaultdict(int)
        """:type: dict[Aircraft, int]"""
        third_party_rankings = collections.defaultdict(int)
        """:type: dict[Aircraft, int]"""
        any_party_rankings = collections.defaultdict(int)
        """:type: dict[Aircraft, int]"""

        for row in results_rows:
            val = str_to_int(row[1])
            if 'Class:' not in row[0]:  # this row got weirdly truncated... nothing to be done here
                continue
            aircraft = Aircraft.from_str(row[0])
            any_party_rankings[aircraft] += val
            if aircraft.is_first_party():
                first_party_rankings[aircraft] += val
            else:
                third_party_rankings[aircraft] += val
        return AircraftStats(first_party=first_party_rankings, third_party=third_party_rankings, combined=any_party_rankings)


@dataclass
class AcfStatGrapher:
    acf_stats: AircraftStats

    def first_vs_third_party(self, with_title=False):
        vals = [self.acf_stats.first_party_flights / self.acf_stats.total_flights, self.acf_stats.third_party_flights / self.acf_stats.total_flights]
        first_vs_third_party_pie_chart = plotly.graph_objs.Pie(
            labels=['Laminar Research', 'Third Party'],
            values=vals,
            textinfo='label+percent',
            #textfont=dict(size=36)
        )
        return plotly.graph_objs.Figure(data=[first_vs_third_party_pie_chart],
                                        layout=plotly.graph_objs.Layout(showlegend=False,
                                                                        title='First- vs. Third-Party Aircraft Usage' if with_title else None))

    def top_third_party(self, with_title=False):
        third_party_flights = self.acf_stats.third_party
        reverse_sorted = reversed(sort_dict_by_value(third_party_flights))
        third_party = collections.OrderedDict()
        third_party["Other"] = 0
        for i, acf in enumerate(reverse_sorted):
            if len(third_party_flights) - 10 < i < len(third_party_flights):
                if 'Zibo and Twkster' in acf.studio:
                    key = 'Zibo and Twkster ' + acf.name
                else:
                    key = acf.studio + ' ' + acf.name
                if ' and ' in key:
                    key = key.replace(' and ', ' & ')
                third_party[key] = third_party_flights[acf]
            else:
                third_party["Other"] += third_party_flights[acf]
        return make_bar_chart_figure(third_party, '', y_label='% Third-Party Aircraft Flights', needs_conversion_to_percents=True, height_scaling_factor=1, horizontal=True, already_sorted=True, y_axis_size=16)

    def top_first_party(self, with_title=False):
        flights = self.acf_stats.first_party
        reverse_sorted = reversed(sort_dict_by_value(flights))
        out = collections.OrderedDict()
        out["Other"] = 0
        for i, acf in enumerate(reverse_sorted):
            if len(flights) - 10 < i < len(flights):
                out[acf.name] = flights[acf]
            else:
                out["Other"] += flights[acf]
        return make_bar_chart_figure(out, '', y_label='% First-Party Aircraft Flights',
                                     needs_conversion_to_percents=True,
                                     horizontal=True, already_sorted=True,
                                     title='Top First-Party Aircraft' if with_title else None)

    def categories(self, with_title=False):
        categories_with_other = counts_to_percents(self.acf_stats.categories, self.acf_stats.total_flights, smush_into_other_below_percent=2)
        return make_bar_chart_figure(categories_with_other, '', y_label='% Flights',
                                     needs_conversion_to_percents=False, already_sorted=True,
                                     title='Flights by Aircraft Category' if with_title else None)


def perform_aircraft_analysis(version, user_group):
    global file_name_suffix
    file_name_suffix = "_%s_%s_%s" % (version.name, user_group.name, today_file_suffix())

    service = GaService.desktop()
    rankings = AircraftStats.from_ga(service, version, user_group)

    prolific_studios = {}
    for studio in sorted(['Carenado', 'Flight Factor', 'Thranda Design', 'Alabeo', 'FlyJSim', 'dmax3d.com', 'Aerobask', 'JustFlight', 'X-Crafts', 'XPFR', 'Other']):
        prolific_studios[studio] = {acf: flights for acf, flights in rankings.third_party.items() if studio in acf.studio}

    if SHOW_ABSOLUTE_NUMBERS:
        writer = AbsoluteNumbersAnalysisWriter('aircraft_analysis')
    else:
        writer = AnalysisWriter('aircraft_analysis')
    writer.dump_dict("AIRCRAFT CATEGORIES (BY POPULARITY)", rankings.categories,  rankings.total_flights)
    writer.dump_dict("FIRST PARTY PLANES (BY POPULARITY)",  rankings.first_party, rankings.total_flights)
    writer.dump_dict("THIRD PARTY PLANES (BY POPULARITY)",  rankings.third_party, rankings.total_flights)
    writer.dump_dict("ALL PLANES (BY POPULARITY)",          rankings.combined,    rankings.total_flights)

    # for studio, studio_acf in prolific_studios.items():
    #     writer.dump_dict('Aircraft from ' + studio,         studio_acf,           rankings.total_flights)

    grapher = AcfStatGrapher(rankings)
    plotly.offline.plot(grapher.first_vs_third_party(), image='png', image_filename='first_vs_third_party' + file_name_suffix, image_width=1024, output_type='file')

    categories_with_other = counts_to_percents(rankings.categories, rankings.total_flights, smush_into_other_below_percent=2)
    make_bar_chart(categories_with_other, 'aircraft_categories' + file_name_suffix, 'Aircraft Classification', y_label='% Flights', needs_conversion_to_percents=False, already_sorted=True, height_scaling_factor=1.2, x_axis_size=22)

    third_party = collections.OrderedDict()
    third_party["Other 3rd-party aircraft"] = 0
    for i, (acf, flights) in enumerate(analytics_utils.sort_dict_by_value(rankings.third_party).items()):
        if i < 10:
            key = acf.studio + ' ' + acf.name
            if 'Zibo and Twkster' in key:
                key = 'Zibu & Twkster ' + acf.name
            if ' and ' in key:
                key = key.replace(' and ', ' & ')
            third_party[key] = flights
        else:
            third_party["Other 3rd-party aircraft"] += flights
    make_bar_chart(third_party, 'top_third_party_aircraft' + file_name_suffix, '', y_label='% Third Party Aircraft Flights', needs_conversion_to_percents=True, height_scaling_factor=1, horizontal=True, already_sorted=False)


def main():
    argparser = argparse.ArgumentParser(description='Dumps aircraft usage data from X-Plane Desktop; you probably want to pipe the output to a CSV file')
    argparser.add_argument('--version', type=int, default=11, help='The major version of X-Plane you want data on (10 or 11)')

    args = argparser.parse_args()

    perform_aircraft_analysis(Version.v11 if args.version == 11 else Version.v10, UserGroup.PaidOnly)



if __name__ == '__main__':
    main()