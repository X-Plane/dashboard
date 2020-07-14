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
from gateway import GatewayGrapher
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
        if row[0] != '<REGION>':
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

gateway = GatewayGrapher()
color_orange = 'rgb(255, 127, 14)'

service = GaService.desktop()

acf_rankings = AircraftStats.from_ga(service, Version.v11, UserGroup.PaidOnly)
grapher = AcfStatGrapher(acf_rankings)

hardware = HardwareStats(service)
hw_grapher = HardwareGrapher(hardware)

app.layout = html.Div([
                          html.Div([
                          ], className='prose'),
                          html.Div([
                              html.Div([
                                  html.Ol([
                                      html.Li([html.A('Aircraft', href='#aircraft'),
                                               html.Ul([
                                                   html.Li(html.A('First- vs. Third-Party Aircraft Usage', href='#first-vs-third-party-heading')),
                                                   html.Li(html.A('Flights by Aircraft Category', href='#categories-heading')),
                                                   html.Li(html.A('Top Third-Party Aircraft', href='#top-third-party-heading')),
                                                   html.Li(html.A('Top First-Party Aircraft', href='#top-first-party-heading')),
                                               ])]),
                                       html.Li(html.A('Top Starting Locations', href='#locations-heading')),
                                       html.Li([html.A('Hardware', href='#hardware'),
                                               html.Ul([
                                                   html.Li(html.A('RAM', href='#ram-heading')),
                                                   html.Li(html.A('Graphics Card Manufacturer', href='#gpu-mfr-heading')),
                                                   html.Li(html.A('Users Who Have Flown in VR in 2019', href='#vr-usage-heading')),
                                                   html.Li(html.A('VR Headsets in Use', href='#vr-headsets-heading')),
                                               ])]),
                                       html.Li(html.A('Operating Systems', href='#os-heading')),
                                      html.Li([html.A('X-Plane Scenery Gateway', href='#gateway'),
                                               html.Ul([
                                                   html.Li(html.A('3-D Gateway Airports', href='#gateway-3d-heading')),
                                                   html.Li(html.A('Total Submitted Gateway Scenery Packs', href='#gateway-packs-heading')),
                                                   html.Li(html.A('Registered Gateway Artists', href='#gateway-artists-heading')),
                                               ])]),
                                  ], id='table-of-contents'),
                              ], className='prose', style={'width': '33%', 'float': 'right'}),

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
                              ], style={'width': '60%'}),
                          ]),

                          html.H2('Aircraft', id='aircraft', style={'clear': 'both'}),
                          html.Div([
                              html.Div([
                                  html.H3('First- vs. Third-Party Aircraft Usage', className='graph-title', id='first-vs-third-party-heading'),
                                  dcc.Graph(id='first-vs-third-party', figure=grapher.first_vs_third_party()),
                              ], style={'width': '50%', 'float': 'right'}),

                              html.Div([
                                  html.H3('Flights by Aircraft Category', className='graph-title', id='categories-heading'),
                                  dcc.Graph(id='categories', figure=grapher.categories()),
                              ], style={'width': '50%'}),
                          ]),

                          html.H3('Top Third-Party Aircraft', className='graph-title', id='top-third-party-heading'),
                          dcc.Graph(id='third-party-planes', figure=grapher.top_third_party()),

                          html.H3('Top First-Party Aircraft', className='graph-title', id='top-first-party-heading'),
                          dcc.Graph(id='first-party-planes', figure=grapher.top_first_party()),

                          html.Div([
                              html.Div([
                                  html.H2('Top Starting Locations', className='graph-title left', id='locations-heading'),
                                  make_table(['Rank', 'Location', '% Flights'], ((i + 1, loc, "%0.3f%%" % (pct * 10)) for i, (loc, pct) in enumerate(itertools.islice(starting_locations(service), 1, 51)))),
                              ], style={'float': 'right', 'width': '33%'}),

                              html.Div([
                                  html.H2('Hardware', id='hardware'),
                                  html.H3('RAM', className='graph-title', id='ram-heading'),
                                  dcc.Graph(id='ram-amounts', figure=hw_grapher.ram_amounts()),

                                  html.H3('Graphics Card Manufacturer', className='graph-title', id='gpu-mfr-heading'),
                                  dcc.Graph(id='gpu-manufacturer', figure=hw_grapher.gpu_manufacturers()),

                                  html.H3('Users Who Have Flown in VR in 2019', className='graph-title', id='vr-usage-heading'),
                                  # TODO: Fix live reporting...
                                  dcc.Graph(id='vr-usage', figure=make_pie_chart_figure({
                                      'Have Used VR': 2.06,
                                      '2-D Monitor Only': 100 - 2.06
                                  }, top_pad_px=40)),

                                  html.H3('VR Headsets in Use', className='graph-title', id='vr-headsets-heading'),
                                  dcc.Graph(id='vr-headsets', figure=hw_grapher.vr_headsets()),

                                  html.H2('Operating Systems', className='graph-title', id='os-heading'),
                                  dcc.Graph(id='operating-systems', figure=hw_grapher.operating_systems()),
                              ], style={'width': '67%'}),
                          ], style={'margin-top': '2rem'}),

                          html.H2('X-Plane Scenery Gateway', id='gateway'),
                          html.H3('3-D Gateway Airports', className='graph-title', id='gateway-3d-heading'),
                          dcc.Graph(id='gateway-airports-3d', figure=gateway.airports_3d_over_time(color=color_orange)),

                          html.H3('Total Submitted Gateway Scenery Packs', className='graph-title', id='gateway-packs-heading'),
                          dcc.Graph(id='gateway-packs', figure=gateway.total_submissions_over_time()),

                          html.H3('Registered Gateway Artists', className='graph-title', id='gateway-artists-heading'),
                          dcc.Graph(id='gateway-artists', figure=gateway.registered_artists_over_time(color=color_orange)),
                      ],
                      style={'backgroundColor': colors['background']}
)

if __name__ == '__main__':
    app.run_server(debug='DEBUG' in os.environ)
