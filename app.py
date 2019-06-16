#!/bin/env python3
# -*- coding: utf-8 -*-
import itertools
import os
from random import randint
from typing import Iterable, Dict, Tuple, List, Any
import dash
import dash_core_components as dcc
import dash_html_components as html
import flask
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



server = flask.Flask(__name__)
server.secret_key = os.environ.get('secret_key', str(randint(0, 1000000)))
app = dash.Dash(__name__, server=server)

app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Latest X-Plane Usage Data</title>
        <link rel="apple-touch-icon" sizes="57x57" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/apple-touch-icon-57x57.png">
        <link rel="apple-touch-icon" sizes="60x60" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/apple-touch-icon-60x60.png">
        <link rel="apple-touch-icon" sizes="72x72" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/apple-touch-icon-72x72.png">
        <link rel="apple-touch-icon" sizes="76x76" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/apple-touch-icon-76x76.png">
        <link rel="apple-touch-icon" sizes="114x114" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/apple-touch-icon-114x114.png">
        <link rel="apple-touch-icon" sizes="120x120" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/apple-touch-icon-120x120.png">
        <link rel="apple-touch-icon" sizes="144x144" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/apple-touch-icon-144x144.png">
        <link rel="apple-touch-icon" sizes="152x152" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/apple-touch-icon-152x152.png">
        <link rel="apple-touch-icon" sizes="180x180" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/apple-touch-icon-180x180.png">
        <link rel="icon" type="image/png" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/favicon-32x32.png" sizes="32x32">
        <link rel="icon" type="image/png" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/favicon-194x194.png" sizes="194x194">
        <link rel="icon" type="image/png" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/favicon-96x96.png" sizes="96x96">
        <link rel="icon" type="image/png" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/android-chrome-192x192.png" sizes="192x192">
        <link rel="icon" type="image/png" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/favicon-16x16.png" sizes="16x16">
        <link rel="manifest" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/manifest.json">
        <link rel="mask-icon" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/safari-pinned-tab.svg" color="#1678b5">
        <link rel="shortcut icon" href="https://developer.x-plane.com/wp-content/themes/xplane/favicons/favicon.ico">
        <meta name="msapplication-TileColor" content="#da532c">
        <meta name="msapplication-TileImage" content="https://developer.x-plane.com/wp-content/themes/xplane/favicons/mstile-144x144.png">
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

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
                          html.Div([
                              html.H1('X-Plane 11 Usage Data'),
                              html.P('This is the always up-to-date X-Plane usage data page. It updates daily based on data received from users.'),
                              html.P('The data shown here comes only from paying users of the X-Plane 11 simulator who have opted in to data collection.'),
                              html.P(html.A('Learn more about X-Plane\'s opt-in data collection here.', href='https://www.x-plane.com/kb/data-collection-privacy-policy/')),
                              html.P([
                                  'Please report any issues with this dashboard, or file any feature requests, ',
                                  html.A('on the project\'s GitHub page', href='https://github.com/X-Plane/dashboard/issues'),
                                  '.'
                              ]),
                          ], className='prose'),

                          html.H2('Aircraft'),
                          html.Div([
                              html.Div([
                                  html.H3('First- vs. Third-Party Aircraft Usage', className='graph-title'),
                                  dcc.Graph(id='first-vs-third-party', figure=grapher.first_vs_third_party()),
                              ], style={'width': '50%', 'float': 'right'}),

                              html.Div([
                                  html.H3('Flights by Aircraft Category', className='graph-title'),
                                  dcc.Graph(id='categories', figure=grapher.categories()),
                              ], style={'width': '50%'}),
                          ]),

                          html.H3('Top Third-Party Aircraft', className='graph-title'),
                          dcc.Graph(id='third-party-planes', figure=grapher.top_third_party()),

                          html.H3('Top First-Party Aircraft', className='graph-title'),
                          dcc.Graph(id='first-party-planes', figure=grapher.top_first_party()),

                          html.Div([
                              html.Div([
                                  html.H2('Top Starting Locations', className='graph-title left'),
                                  make_table(['Rank', 'Location', '% Flights'], ((i + 1, loc, "%0.4f%%" % (pct * 10)) for i, (loc, pct) in enumerate(itertools.islice(starting_locations(service), 1, 51)))),
                              ], style={'float': 'right', 'width': '33%'}),

                              html.Div([
                                  html.H2('Hardware'),
                                  html.H3('RAM', className='graph-title'),
                                  dcc.Graph(id='ram-amounts', figure=hw_grapher.ram_amounts()),

                                  html.H3('Graphics Card Manufacturer', className='graph-title'),
                                  dcc.Graph(id='gpu-manufacturer', figure=hw_grapher.gpu_manufacturers()),

                                  html.H3('Users Who Have Flown in VR in 2019', className='graph-title'),
                                  dcc.Graph(id='vr-usage', figure=make_pie_chart_figure({
                                      'Have Used VR': 2.06,
                                      '2-D Monitor Only': 100 - 2.06
                                  }, top_pad_px=40)),

                                  html.H3('VR Headsets in Use', className='graph-title'),
                                  dcc.Graph(id='vr-headsets', figure=hw_grapher.vr_headsets()),

                                  html.H2('Operating Systems', className='graph-title'),
                                  dcc.Graph(id='operating-systems', figure=hw_grapher.operating_systems()),
                              ], style={'width': '67%'}),
                          ], style={'margin-top': '2rem'}),

                      ],
                      style={'backgroundColor': colors['background']}
)

if __name__ == '__main__':
    app.run_server(debug='DEBUG' in os.environ)
