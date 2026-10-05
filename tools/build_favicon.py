"""Generate the standalone favicon from the shared Stride emblem."""
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

root_path = Path(__file__).resolve().parents[1]
namespace = 'http://www.w3.org/2000/svg'
ET.register_namespace('', namespace)
source = ET.parse(root_path / 'static/stride-emblem.svg')
mark = source.find(f'.//{{{namespace}}}g')
icon = ET.Element(f'{{{namespace}}}svg', {'viewBox': '0 0 64 64'})
ET.SubElement(icon, f'{{{namespace}}}title').text = 'Stride'
ET.SubElement(icon, f'{{{namespace}}}rect', {
    'width': '64', 'height': '64', 'rx': '16', 'fill': '#204c3e'})
art = ET.SubElement(icon, f'{{{namespace}}}svg', {
    'x': '6', 'y': '6', 'width': '52', 'height': '52', 'viewBox': '0 0 128 128',
    'fill': 'none', 'style': '--stride-track:#d3eaa4;--stride-lane:#204c3e'})
art.append(deepcopy(mark))
ET.ElementTree(icon).write(root_path / 'static/favicon.svg', encoding='utf-8')
