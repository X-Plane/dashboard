#!/bin/env python3
# -*- coding: utf-8 -*-
import itertools
from typing import Iterable, Dict, Tuple, List, Any
import dash
import dash_core_components as dcc
import dash_html_components as html
from aircraft_analysis import AircraftStats, AcfStatGrapher
from utils import make_pie_chart_figure
from ga_library import GaService, Version, UserGroup, CustomDimension
from hardware_analysis import HardwareStats, HardwareGrapher


def make_table(header: Iterable[str], rows: Iterable[Iterable[Any]]) -> html.Table:
    return html.Table([html.Tr([html.Th(col) for col in header])] +

                      [html.Tr([html.Td(val) for val in row])
                       for row in rows])

def starting_locations(service: GaService) -> Iterable[Tuple[str, float]]:
    flight_counts = []
    for row in service.events(11, CustomDimension.Region, override_start_date='2019-04-01'):
        flight_counts.append((row[0], int(row[1])))

    # Convert absolute numbers to percents
    total_flights = sum(count for loc, count in flight_counts)
    for loc, count in flight_counts:
        yield loc, count / total_flights



app = dash.Dash(__name__, external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css'])

colors = {
    'background': '#ffffff',
    'text': '#333'
}

service = GaService.desktop()

acf_rankings = AircraftStats.from_ga(service, Version.v11, UserGroup.PaidOnly)
grapher = AcfStatGrapher(acf_rankings)

hardware = HardwareStats(service)
hw_grapher = HardwareGrapher(hardware)

app.layout = html.Div([
                          # html.H1('Hello Dash',
                          #         style={
                          #             'textAlign': 'center',
                          #             'color': colors['text']
                          #         }),
                          #
                          # html.Div('Dash: A web application framework for Python.',
                          #          style={
                          #              'textAlign': 'center',
                          #              'color': colors['text']
                          #          }),

                          html.H2('Aircraft'),
                          html.H3('Flights by Aircraft Category', className='graph-title'),
                          dcc.Graph(id='categories', figure=grapher.categories()),

                          html.H3('First- vs. Third-Party Aircraft Usage', className='graph-title'),
                          dcc.Graph(id='first-vs-third-party', figure=grapher.first_vs_third_party()),

                          html.H3('Top Third-Party Aircraft', className='graph-title'),
                          dcc.Graph(id='third-party-planes', figure=grapher.top_third_party()),

                          html.H3('Top First-Party Aircraft', className='graph-title'),
                          dcc.Graph(id='first-party-planes', figure=grapher.top_first_party()),

                          html.H2('Top Starting Locations', className='graph-title'),
                          make_table(['Rank', 'Location', '% Flights'], ((i, loc, "%0.4f%%" % (pct * 10)) for i, (loc, pct) in enumerate(itertools.islice(starting_locations(service), 50)) if loc != '<REGION>')),

                          html.H2('Operating Systems'),
                          dcc.Graph(id='operating-systems', figure=hw_grapher.operating_systems()),

                          html.H2('Hardware'),
                          html.H3('RAM'),
                          dcc.Graph(id='ram-amounts', figure=hw_grapher.ram_amounts()),

                          html.H3('Graphics Card Manufacturer'),
                          dcc.Graph(id='gpu-manufacturer', figure=hw_grapher.gpu_manufacturers()),

                          # html.H3('Desktop vs. Mobile GPUs'),
                          # dcc.Graph(id='gpu-platform', figure=hw_grapher.gpu_mobile_vs_desktop()),

                          html.H3('VR Headsets in Use'),
                          dcc.Graph(id='vr-headsets', figure=hw_grapher.vr_headsets()),

                          html.H3('% Users Who Have Flown in VR in 2019'),
                          dcc.Graph(id='vr-usage', figure=make_pie_chart_figure({
                              'Has Used VR': 2.06,
                              '2-D Monitor Only': 100 - 2.06
                          })),
                      ],
                      style={'backgroundColor': colors['background']}
)

if __name__ == '__main__':
    app.run_server(debug=False)
