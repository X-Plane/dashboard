from __future__ import division
import operator
import re
import plotly
from collections import OrderedDict, defaultdict
from datetime import date
from typing import Dict, Union, Optional


def classify_platform(os_string):
    """
    :type os_string: str
    :return: str
    """
    os_string = os_string.strip()
    if os_string == "Windows" or os_string.startswith("IBM"):
        return "Windows"
    elif os_string == "Mac" or os_string.startswith("APL"):
        return "Mac"
    elif os_string == "Linux" or os_string.startswith("LIN"):
        return "Linux"
    else:
        return "Dafuq?"


def get_os_version(row_os_cell):
    """
    :type row_os_cell: str
    :return: str
    """
    row_os_cell = row_os_cell.strip()
    version_name = ""

    if row_os_cell.startswith("IBM"):
        version_name = "Windows "
        version_raw = row_os_cell[3:]
        if version_raw.startswith("10."):
            version_name += version_raw[:4]
        elif version_raw.startswith("6.3"):
            version_name += "8.1"
        elif version_raw.startswith("6.2"):
            version_name += "8.0"
        elif version_raw.startswith("6.1"):
            version_name += "7"
        elif version_raw.startswith("6.0"):
            version_name += "Vista"
        elif version_raw.startswith("5"):
            version_name += "XP"

        bit_depth = " 64-bit"
        if "_32_" in row_os_cell:
            bit_depth = " 32-bit"
        version_name += bit_depth
    elif row_os_cell.startswith("APL"):
        version_name = "\"OSX " + re.match("(^[0-9][0-9]\.[0-9]+)", row_os_cell[3:]).groups()[0] + "\""
    elif row_os_cell.startswith("LIN"):
        bit_depth = " 64-bit"
        if "32bit" in row_os_cell:
            bit_depth = " 32-bit"
        version_name = "Linux" + bit_depth
    return version_name

def today_file_suffix():
    today = date.today()
    return "%d_%d_%d" % (today.year, today.month, today.day)


def total_entries_in_dict(key_count_dict):
    total = 0
    for label, count in key_count_dict.items():
        total += count
    return total

def sort_dict_by_value(d, reverse=True):
    return OrderedDict(sorted(d.items(), key=operator.itemgetter(1), reverse=reverse))

def make_bar_chart_figure(data_dict, x_label, y_label='% Users', x_axis_size=16, y_axis_size=14, make_x_label=lambda l: str(l), horizontal=False, height_scaling_factor=1, needs_conversion_to_percents=False, already_sorted=False, title=None):
    import plotly
    sorted_data = data_dict if already_sorted else sort_dict_by_value(data_dict)
    if needs_conversion_to_percents:
        sorted_data = counts_to_percents(sorted_data)

    x = [make_x_label(label) for label in sorted_data.keys()]
    y = list(sorted_data.values())
    bar_chart = plotly.graph_objs.Bar(
        x=y if horizontal else x,
        y=x if horizontal else y,
        text=["%0.1f%%" % val for val in sorted_data.values()],
        textposition='auto',
        orientation='h' if horizontal else 'v'
    )
    return plotly.graph_objs.Figure(data=[bar_chart],
                                    layout=plotly.graph_objs.Layout(
                                        showlegend=False,
                                        title=title,
                                        xaxis=dict(tickfont=dict(size=x_axis_size), title=y_label if horizontal else x_label, automargin=True),
                                        yaxis=dict(tickfont=dict(size=y_axis_size), title=x_label if horizontal else y_label, automargin=True),
                                        margin=dict(t=0, b=0, pad=0)
                                    ))

def make_absolute_bar_chart_figure(ordered_data_dict, x_label, y_label, x_axis_size=16, y_axis_size=14, make_x_label=lambda l: str(l), horizontal=False, title=None, bar_color: Optional[str]=None):
    import plotly
    x = [make_x_label(label) for label in ordered_data_dict.keys()]
    y = list(ordered_data_dict.values())
    bar_chart = plotly.graph_objs.Bar(
        x=y if horizontal else x,
        y=x if horizontal else y,
        textposition='auto',
        orientation='h' if horizontal else 'v',
        marker=dict(color=bar_color)
    )
    return plotly.graph_objs.Figure(data=[bar_chart],
                                    layout=plotly.graph_objs.Layout(
                                        showlegend=False,
                                        title=title,
                                        xaxis=dict(tickfont=dict(size=x_axis_size), title=y_label if horizontal else x_label, automargin=True),
                                        yaxis=dict(tickfont=dict(size=y_axis_size), title=x_label if horizontal else y_label, automargin=True),
                                        margin=dict(t=0, b=0, pad=0)
                                    ))

def make_bar_chart(data_dict, out_file_name, x_label, y_label='% Users', x_axis_size=32, y_axis_size=24, make_x_label=lambda l: str(l), horizontal=False, height_scaling_factor=1, needs_conversion_to_percents=False, already_sorted=False):
    figure = make_bar_chart_figure(data_dict, x_label, y_label, x_axis_size, y_axis_size, make_x_label, horizontal, height_scaling_factor, needs_conversion_to_percents, already_sorted)
    plotly.offline.plot(figure, image='png', output_type='file', image_filename=out_file_name, image_width=1024, image_height=600 * height_scaling_factor)


def make_pie_chart_figure(data_dict, top_pad_px: int=0) -> plotly.graph_objs.Figure:
    chart = plotly.graph_objs.Pie(
        labels=list(data_dict.keys()),
        text=list(data_dict.keys()),
        textfont=dict(size=18),
        values=list(data_dict.values())
    )
    return plotly.graph_objs.Figure(data=[chart],
                                    layout=plotly.graph_objs.Layout(
                                        showlegend=False,
                                        margin=dict(t=top_pad_px, b=0)
                                    ))

def counts_to_percents(count_dict: Dict[str, int], override_total: Union[None, int]=None, smush_into_other_below_percent: float=0):
    total = override_total if override_total else total_entries_in_dict(count_dict)
    out = OrderedDict()
    other_percent = 0
    sorted = count_dict if isinstance(count_dict, OrderedDict) else sort_dict_by_value(count_dict)
    for key, count in sorted.items():
        percent = count / total * 100
        if percent >= smush_into_other_below_percent:
            out[key] = round(percent, 2 if percent < 2 else 1)
        else:
            other_percent += percent
    if other_percent > 0:
        out['Other'] = round(other_percent, 2)
    return out

def str_to_int(as_str):
    return int(as_str.replace(',', ''))

