"""Accesses the Google Analytics API to spit out a CSV of aircraft usage"""

from __future__ import division, print_function
import argparse
import collections
import logging
from ga_library import *
from utils import *
from collections import defaultdict, OrderedDict


SHOW_ABSOLUTE_NUMBERS = False


_out = ''
def _log(s, end='\n'):
    global _out
    _out += s + end


file_name_suffix = ''


def main():
    argparser = argparse.ArgumentParser(description='Dumps hardware stats from X-Plane Desktop; you probably want to pipe the output to a CSV file')
    argparser.add_argument('--version', type=int, default=11, help='The major version of X-Plane you want data on (10 or 11)')

    args = argparser.parse_args()
    write_hardware_analysis_files(Version.v11 if args.version == 11 else Version.v10, UserGroup.PaidOnly)


def write_hardware_analysis_files(version: Union[int, Version], user_group: UserGroup, csv_path=None):
    """
    :type csv_path: Union[str,None]
    """
    global file_name_suffix
    file_name_suffix = "_%s_%s_%s" % (version, user_group.name, today_file_suffix())

    qm = SimpleQueryMgr(GaService.desktop(), version, Metric.Users, user_group)

    perform_cpu_analysis(qm.query(CustomDimension.Cpu))
    perform_flight_controls_analysis(qm.query(CustomDimension.FlightControls))

    stats = HardwareStats(GaService.desktop(), version, Metric.Users, user_group)
    grapher = HardwareGrapher(stats)
    perform_ram_analysis(stats)
    perform_gpu_analysis(stats)
    perform_os_analysis(stats, grapher)
    perform_vr_analysis(stats, grapher)

    if not csv_path:
        csv_path = "hardware_analysis%s.csv" % file_name_suffix
    with open(csv_path, 'w') as out_file:
        out_file.write(_out)
        out_file.write('\n')


class HardwareStats:
    def __init__(self, service: GaService, version: Union[int, Version]=Version.v11, user_group: UserGroup=UserGroup.PaidOnly):
        self.qm = SimpleQueryMgr(service, version, Metric.Users, user_group)

    def operating_systems(self) -> Dict[str, int]:
        platform_count = defaultdict(int)
        for row in self.qm.query(CustomDimension.Os):
            val = str_to_int(row[1])
            os_name = classify_platform(row[0])
            platform_count[os_name] += val
        return counts_to_percents(platform_count)

    def operating_system_versions(self) -> Dict[str, Dict[str, int]]:
        version_count = defaultdict(lambda: defaultdict(int))
        for row in self.qm.query(CustomDimension.Os):
            val = str_to_int(row[1])
            os_name = classify_platform(row[0])
            version = get_os_version(row[0])
            if version:
                version_count[os_name][version] += val
        return version_count

    def ram_amounts(self) -> Dict[str, int]:
        users_with_at_least_this_much_ram = collections.defaultdict(int)
        total_users = 0
        for row in self.qm.query(CustomDimension.Ram):
            val = str_to_int(row[1])
            total_users += val
            ram_class = int(row[0])
            if ram_class >= 2:
                users_with_at_least_this_much_ram["2GB"] += val
            if ram_class >= 4:
                users_with_at_least_this_much_ram["4GB"] += val
            if ram_class >= 8:
                users_with_at_least_this_much_ram["8GB"] += val
            if ram_class >= 16:
                users_with_at_least_this_much_ram["16GB"] += val
            if ram_class >= 32:
                users_with_at_least_this_much_ram["32GB"] += val
        return counts_to_percents(users_with_at_least_this_much_ram, total_users)

    def gpu_manufacturers(self) -> Dict[str, int]:
        out = defaultdict(int)
        for row in self.qm.query(CustomDimension.Gpu):
            out[get_gpu_manufacturer(row[0])] += str_to_int(row[1])
        out = counts_to_percents(out)

        with suppress(KeyError):
            if out['Unknown'] < 0.3:
                del out['Unknown']

        return out


    def gpu_generation(self) -> Dict[str, int]:
        out = defaultdict(int)
        for row in self.qm.query(CustomDimension.Gpu):
            out[get_gpu_generation(row[0])] += str_to_int(row[1])
        return counts_to_percents(out)

    def gpu_platform(self) -> Dict[str, int]:
        out = defaultdict(int)
        for row in self.qm.query(CustomDimension.Gpu):
            out[get_mobile_versus_desktop(row[0])] += str_to_int(row[1])
        return counts_to_percents(out)

    def vr_headsets(self):
        known_headsets = {
            'rift': 'Oculus Rift',
            'oculus': 'Oculus Rift',
            'pimax 5k': 'Pimax 5K',
            'psvr': 'PSVR Headset',
            'windows': 'Windows Mixed Reality',
            'lighthouse': 'OpenVR (like HTC Vive)',
            'vive': 'OpenVR (like HTC Vive)',
            'aapvr': 'Phone',
            'vridge': 'Phone',
            'ivry': 'Phone',
            'phonevr': 'Phone',
        }
        headset_count = collections.defaultdict(int)
        for row in self.qm.query(CustomDimension.VrHeadset):
            label = row[0]
            for search_term, deduped_name in known_headsets.items():
                if search_term in label.lower():
                    label = deduped_name
                    break
            else:
                logging.debug('unknown headset: ' + label)
            headset_count[label] += str_to_int(row[1])
        return counts_to_percents(headset_count, smush_into_other_below_percent=1)

    def vr_usage(self):
        vr_start_date = Version.v1120r4.value.start_date
        total_users = sum(str_to_int(row[1]) for row in self.qm.query(CustomDimension.Ram, override_start_date=vr_start_date))
        vr_users = sum(str_to_int(row[1]) for row in self.qm.query(CustomDimension.VrHeadset, override_start_date=vr_start_date))
        vr_pct = round((vr_users / total_users) * 100, 2)
        return {
            'Have Used VR': vr_pct,
            '2-D Monitor Only': 100 - vr_pct
        }

    @property
    def total_users(self):
        ram_data = self.qm.query(CustomDimension.Ram)
        return sum(str_to_int(row[1]) for row in ram_data)


class HardwareGrapher:
    def __init__(self, stats: HardwareStats):
        self.stats = stats

    def operating_systems(self) -> plotly.graph_objs.Figure:
        return make_pie_chart_figure(self.stats.operating_systems())

    def ram_amounts(self) -> plotly.graph_objs.Figure:
        return make_bar_chart_figure(self.stats.ram_amounts(), 'Users with at Least <em>x</em> GB RAM', make_x_label=lambda l: str(l) + '+')

    def gpu_mobile_vs_desktop(self) -> plotly.graph_objs.Figure:
        return make_pie_chart_figure(self.stats.gpu_platform())

    def gpu_manufacturers(self) -> plotly.graph_objs.Figure:
        return make_bar_chart_figure(self.stats.gpu_manufacturers(), 'GPU Manufacturers')

    def vr_headsets(self) -> plotly.graph_objs.Figure:
        return make_bar_chart_figure(self.stats.vr_headsets(), 'VR Headsets', already_sorted=True, y_label='% VR Users')

    def vr_usage(self) -> plotly.graph_objs.Figure:
        return make_pie_chart_figure(self.stats.vr_usage(), top_pad_px=40)


def perform_os_analysis(stats: HardwareStats, grapher: HardwareGrapher):
    # Overall platform breakdown
    platform_count = stats.operating_systems()

    _log("PLATFORM BREAKDOWN")
    dump_generic_count_dict(platform_count, "Operating System", "Machines")

    plotly.offline.plot(grapher.operating_systems(), image='png', image_filename='os_breakdown' + file_name_suffix, image_width=1024, output_type='file')

    version_count = stats.operating_system_versions()
    _log("OS VERSIONS")
    dump_generic_count_dict(version_count["Windows"], "OS Version", "Windows Machines")
    dump_generic_count_dict(version_count["Mac"], "OS Version", "Macs")
    dump_generic_count_dict(version_count["Linux"], "OS Version", "Linux Machines")



def clean_up_string_formatting(string):
    return str(string).strip()


def perform_cpu_analysis(results_rows):
    def get_cpu_core_count(cpu_line):
        stats = cpu_line.split(" - ")
        for stat in stats:
            if stat.startswith("Cores:"):
                label_and_cores = stat.split(" ")
                return int(label_and_cores[1])
        return 0

    cpu_cores = collections.defaultdict(int)
    for row in results_rows:
        val = str_to_int(row[1])
        core_count = get_cpu_core_count(row[0])
        cpu_cores[core_count] += val

    _log("NUMBER OF CPU CORES")
    dump_generic_count_dict(cpu_cores, "CPU Cores", "Machines")


def perform_vr_analysis(stats: HardwareStats, grapher: HardwareGrapher):
    _log("VR USAGE")
    dump_generic_count_dict(stats.vr_usage(), "VR Status", "Users")
    _log("VR HEADSETS")
    dump_generic_count_dict(stats.vr_headsets(), "Headset Type", "Users")

    plotly.offline.plot(grapher.vr_usage(), image='png', image_filename='vr_usage' + file_name_suffix, image_width=1024, output_type='file')
    plotly.offline.plot(grapher.vr_headsets(), image='png', image_filename='vr_headsets' + file_name_suffix, image_width=1024, output_type='file')


def get_gpu_manufacturer(gpu_string):
    if lower_contains(gpu_string, ('firepro', 'firegl', 'radeon', 'amd ')) or gpu_string.startswith(('67EF', '67DF', 'ASUS EAH', 'ASUS R')):
        return "AMD/ATI"
    elif lower_contains(gpu_string, ('Quadro', 'GeForce', 'TITAN')) or gpu_string.startswith(('NVS ', 'NV1')):
        return "Nvidia"
    elif "Intel" in gpu_string:
        return "Intel"
    return "Unknown"

def get_gpu_generation(gpu_string):
    gpu = gpu_string.lower()
    if "quadro" in gpu:
        return "Nvidia Quadro (All Generations)"
    elif "firepro" in gpu or "firegl" in gpu:
        return "AMD FirePro (All Generations)"
    if "radeon" in gpu or "asus" in gpu:
        for gen in [2, 3, 4, 5, 6, 7, 8, 9]:
            gen = str(gen)
            if "R" + gen + " M" in gpu_string:
                return "Radeon R" + gen + "M"
            elif "R" + gen + " " in gpu_string:
                return "Radeon R" + gen
            elif re.search(gen + "\d\d\dM", gpu_string) or ("Mobility" in gpu_string and re.search(gen + "\d\d\d", gpu_string)):
                return "Radeon " + gen + "xxxM"
            elif re.search(gen + "\d\d\d", gpu_string):
                return "Radeon " + gen + "xxxM"
        else:
            return "Radeon (Other)"
    elif "titan x" in gpu:
        return "GeForce 9xx"
    elif "titan" in gpu:
        return "GeForce 7xx"
    elif "geforce" in gpu:
        for gen in [1, 2, 3, 4, 5, 6, 7, 8, 9]:
            gen = str(gen)
            base_radeon_re = "GeForce (G|GT|GTX|GTS)?\s*"
            if re.search(base_radeon_re + gen + "\d\d\s*(Ti)?(\s|/)", gpu_string):
                return "GeForce " + gen + "xx"
            elif re.search(base_radeon_re + gen + "\d\dM", gpu_string):
                return "GeForce " + gen + "xxM"
            elif re.search(base_radeon_re + gen + "\d\d\d\s*(Ti)?(\s|/)", gpu_string):
                return "GeForce " + gen + "xxx"
            elif re.search(base_radeon_re + gen + "\d\d\dM", gpu_string):
                return "GeForce " + gen + "xxxM"
        else:
            return "GeForce (Other)"
    elif "intel" in gpu:
        if any(ident in gpu for ident in ["gma", "gm45", "g41", "g45", "q45", "eaglelake", "4 series"]):
            return "Intel Integrated (GMA or earlier)"
        elif "hd" in gpu or "iris" in gpu:
            if any(ident in gpu for ident in ["2000", "3000"]):
                return "Intel Integrated (6th Generation; HD 2000/3000)"
            elif any(ident in gpu for ident in ["4000", "4200", "4400", "4600", "4700", "5000", "5100", "5200"]):
                return "Intel Integrated (7th Generation; HD 2500/4x00/5x00)"
            elif any(ident in gpu_string for ident in ["5300", "5500", "5600", "5700", "6000", "6100", "6200", "6300"]):
                return "Intel Integrated (8th Generation; HD 5x00/6x00)"
            elif any(ident in gpu_string for ident in ["500", "505", "510", "515", "520", "530", "540", "550", "580"]):
                return "Intel Integrated (9th Generation; HD 5xx)"
            else:
                return "Intel Integrated (5th Generation; HD)"
        elif "sandybridge" in gpu:
            return "Intel Integrated (6th Generation; HD 2000/3000)"
        elif "haswell" in gpu or "ivybridge" in gpu or "bay trail" in gpu:
            return "Intel Integrated (7th Generation; HD 2500/4x00/5x00)"
        elif "broadwell" in gpu:
            return "Intel Integrated (8th Generation; HD 5x00/6x00)"
        elif "skylake" in gpu:
            return "Intel Integrated (9th Generation; HD 5xx)"
        elif "ironlake" in gpu:
            return "Intel Integrated (5th Generation; HD)"
        else:
            return gpu_string
    return "Other"

def get_mobile_versus_desktop(gpu_string):
    gen = get_gpu_generation(gpu_string)
    if gen.startswith("Intel"):
        return "Intel"
    elif gen.endswith("M"):
        return "Mobile"
    else:
        return "Desktop"

def perform_gpu_analysis(stats: HardwareStats):
    gpu_manufacturer = stats.gpu_manufacturers()

    _log("GPU PLATFORM")
    dump_generic_count_dict(stats.gpu_platform(), "GPU Platform", "Machines")
    _log("GPU MANUFACTURER")
    dump_generic_count_dict(gpu_manufacturer, "GPU Manufacturer", "Machines")
    _log("GPU GENERATION")
    dump_generic_count_dict(stats.gpu_generation(), "GPU Generation", "Machines")

    with suppress(KeyError):
        del gpu_manufacturer['Unknown']
    make_bar_chart(gpu_manufacturer, 'gpu_manufacturer' + file_name_suffix, 'Manufacturer', needs_conversion_to_percents=False, height_scaling_factor=0.7)


def perform_ram_analysis(stats: HardwareStats):
    users_with_at_least_this_much_ram = stats.ram_amounts()

    _log("USERS WITH AT LEAST THIS MUCH RAM")
    for ram_amount, value in users_with_at_least_this_much_ram.items():
        _log(','.join([str(ram_amount), str(value)]))
    _log("\n" * 3)

    make_bar_chart(users_with_at_least_this_much_ram, 'ram_amounts' + file_name_suffix, 'RAM Amount', make_x_label=lambda l: str(l) + '+', height_scaling_factor=0.7)


def perform_flight_controls_analysis(results_rows):
    known_yokes = [
        "Saitek Pro Flight Yoke",
        "Saitek X52",
        "CH FLIGHT SIM YOKE",
        "CH ECLIPSE YOKE",
        "Pro Flight Cessna Yoke",
        "PFC Cirrus Yoke",
        "CH 3-Axis 10-Button POV USB Yoke",
    ]
    known_sticks = [
        "Logitech 3D Pro",
        "T.Flight Hotas",
        "T.Flight Stick X",
        "Logitech Attack 3",
        "Mad Catz F.L.Y.5 Stick",
        "SideWinder Precision 2",
        "T.16000M",
        "SideWinder Force Feedback 2",
        "Saitek Pro Flight X-55 Rhino Stick",
        "Cyborg",
        "Saitek Cyborg USB Stick",
        "AV8R",
        "Logitech Freedom 2.4",
        "SideWinder Joystick",
        "Mad Catz V.1 Stick",
        "SideWinder Precision Pro",
        "SideWinder 3D Pro",
        "Logitech Force 3D Pro",
        "WingMan Force 3D",
        "Joystick - HOTAS Warthog",
        "WingMan Extreme Digital 3D",
        "WingMan Extreme 3D",
        "Top Gun Afterburner",
        "CH FLIGHTSTICK PRO",
        "CH FIGHTERSTICK",
        "CH COMBATSTICK",
        "Saitek ST290",
        "Saitek ST90",
        "Top Gun Fox 2",
        "Aviator for Playstation 3",
        "Dark Tornado Joystick",
        "Saitek X45",
        "Saitek X36",
        "USB Joystick",
        "Pro Flight X65",
        "G940",
        "HOTAS Cougar Joystick",
        "MetalStrik 3D",
        "WingMan Attack 2"
    ]
    known_controllers = [
        "XBOX",
        "Playstation(R)3 Controller",
        "WingMan Cordless Gamepad",
        "WingMan RumblePad",
        "Logitech Dual Action",
        "RumblePad 2",
        "ASUS Gamepad",
        "USB WirelessGamepad",
        "Betop Controller",
        "Logitech(R) Precision(TM) Gamepad",
        "Wireless Gamepad F710"
    ]
    known_rc_controllers = [
        "InterLink Elite",
        "RealFlight Interface"
    ]
    def canonicalize_stick_or_yoke_name(flight_control_row):
        flight_control_row = clean_up_string_formatting(flight_control_row)
        if "Mouse" in flight_control_row:
            return "Mouse"
        elif "VID:1133PID:49685" in flight_control_row:
            return "Logitech Extreme 3D"
        elif "WingMan Ext Digital 3D" in flight_control_row:
            return "WingMan Extreme Digital 3D"
        elif "VID:1699PID:1890" in flight_control_row:
            return "Saitek X52"
        elif "Wireless 360 Controller" in flight_control_row:
            return "XBOX"
        elif "VID:121PID:6" in flight_control_row:
            return "Generic USB Joystick"
        elif "VID:1678PID:49402" in flight_control_row:
            return "CH Products (Unknown)"
        for control in known_yokes + known_sticks + known_controllers:
            if control.lower() in flight_control_row.lower():
                return control
        if "," in flight_control_row:
            return flight_control_row.replace(",", ";")
        return flight_control_row
    def classify_stick_or_yoke(flight_control_row):
        flight_control_row = canonicalize_stick_or_yoke_name(flight_control_row)
        if flight_control_row == "Mouse":
            return "Mouse"
        elif flight_control_row in known_yokes:
            return "Yoke"
        elif flight_control_row in known_sticks:
            return "Joystick"
        elif flight_control_row in known_controllers:
            return "Gamepad"
        elif flight_control_row in known_rc_controllers:
            return "RC Controller"
        elif "yoke" in flight_control_row.lower():
            return "Yoke"
        elif "stick" in flight_control_row.lower():
            return "Joystick"
        elif "pad" in flight_control_row.lower():
            return "Gamepad"
        else:
            return "Unknown"

    flight_controls = collections.defaultdict(int)
    flight_control_type = collections.defaultdict(int)
    has_rudder_pedals = collections.defaultdict(int)
    for row in results_rows:
        val = str_to_int(row[1])
        flight_controls[canonicalize_stick_or_yoke_name(row[0])] += val
        flight_control_type[classify_stick_or_yoke(row[0])] += val

        row = clean_up_string_formatting(row[0])
        if "rudder" in row.lower() or "pedals" in row.lower():
            has_rudder_pedals[True] += val
        else:
            has_rudder_pedals[False] += val

    nuke_these_keys = []
    for controls, count in flight_controls.items():
        if count < 5:
            nuke_these_keys.append(controls)
    for key in nuke_these_keys:
        flight_controls["Other"] += flight_controls[key]
        del flight_controls[key]

    _log("PRIMARY FLIGHT CONTROLS TYPE")
    dump_generic_count_dict(flight_control_type, "Flight Controls Type", "Users")

    _log("PRIMARY FLIGHT CONTROLS MODEL (for non-mouse users)")
    del flight_controls["Mouse"]
    dump_generic_count_dict(flight_controls, "Flight Controls Model", "Users")

    _log("USERS FLYING WITH PEDALS")
    dump_generic_count_dict(has_rudder_pedals, "Has Pedals?", "Users")



def dump_generic_count_dict(dictionary, label, metric_category):
    if SHOW_ABSOLUTE_NUMBERS:
        _log(label + ",Num " + metric_category + ",% of All " + metric_category)
    else:
        _log(label + ",% of All " + metric_category)
    total = total_entries_in_dict(dictionary)
    sorted_dict = sorted(dictionary.items(), key=operator.itemgetter(1), reverse=True)
    for i, label_and_count in enumerate(sorted_dict):
        if SHOW_ABSOLUTE_NUMBERS:
            _log(','.join([str(label_and_count[0]), str(label_and_count[1]), str((label_and_count[1] / total) * 100) + "%"]))
        else:
            # Coerce to ASCII
            label = clean_up_string_formatting(label_and_count[0])
            percent_str = clean_up_string_formatting(str((label_and_count[1] / total) * 100) + u"%")
            _log(label, end="")
            _log(",", end="")
            _log(percent_str)
    _log("\n" * 3)


def lower_contains(s: str, check: Iterable[str]) -> bool:
    return any(sub.lower() in s.lower() for sub in check)


if __name__ == '__main__':
    main()
