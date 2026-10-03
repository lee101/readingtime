from __future__ import annotations

import argparse
import html
import math
import os
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "manuscripts" / "infographics"
WIDTH = 1400
HEIGHT = 1000

TOPICS = [
    {
        "slug": "36-the-cloud-that-shared-its-rain",
        "level": "accessible",
        "title": "The Cloud That Shared Its Rain",
        "subtitle": "A water-cycle field guide for young observers",
        "kind": "water",
        "accent": "#55c8f2",
        "cards": [
            ("Energy in", "The Sun warms water. Some liquid becomes invisible vapor and rises into the air."),
            ("Cloud clues", "Cooler air makes vapor condense into tiny droplets around dust. Many droplets together make a cloud."),
            ("Return trip", "Drops grow, fall as rain or snow, collect in rivers and soil, and evaporate again."),
        ],
        "footer": "Observe: a cold bottle and a warm wet street show water changing state.",
    },
    {
        "slug": "37-the-seed-that-trapped-a-sunbeam",
        "level": "accessible",
        "title": "The Seed That Trapped a Sunbeam",
        "subtitle": "How a leaf makes food for a growing plant",
        "kind": "photosynthesis",
        "accent": "#7bd66b",
        "cards": [
            ("Light catcher", "Chlorophyll in chloroplasts absorbs light energy from the Sun."),
            ("Ingredients", "Roots bring water up; stomata let carbon dioxide enter the leaf."),
            ("Products", "The plant uses energy to build sugars for growth and releases oxygen into the air."),
        ],
        "footer": "The leaf is a tiny energy factory, not a solar panel made of metal.",
    },
    {
        "slug": "38-why-the-sky-said-blue",
        "level": "accessible",
        "title": "Why the Sky Said Blue",
        "subtitle": "Light, air, and the color that reaches your eyes",
        "kind": "sky",
        "accent": "#6fa8ff",
        "cards": [
            ("Tiny particles", "Air is made of molecules much smaller than the wavelength of visible light."),
            ("Scattering", "Short blue wavelengths scatter in many directions more strongly than longer red wavelengths."),
            ("Sunset clue", "At sunset, light travels a longer path through air, so more red and orange reaches us."),
        ],
        "footer": "The sky is blue because our atmosphere redirects sunlight toward our eyes.",
    },
    {
        "slug": "39-the-magnet-with-two-moods",
        "level": "accessible",
        "title": "The Magnet with Two Moods",
        "subtitle": "A field guide to poles, fields, and electromagnets",
        "kind": "magnet",
        "accent": "#d88bff",
        "cards": [
            ("Two poles", "A bar magnet has north and south poles. Opposite poles attract; like poles repel."),
            ("Invisible pattern", "The magnetic field surrounds the magnet. Iron filings trace its direction."),
            ("Coil trick", "Electric current through a coil creates a magnetic field; a soft core can strengthen an electromagnet."),
        ],
        "footer": "A magnet does not pull every object equally: iron responds strongly; plastic does not.",
    },
    {
        "slug": "30-the-bridge-that-counted-forces",
        "level": "intermediate",
        "title": "The Bridge That Counted Forces",
        "subtitle": "How loads travel through a structure",
        "kind": "bridge",
        "accent": "#ffb454",
        "cards": [
            ("Load path", "Weight enters the deck, moves through beams and supports, then reaches the ground."),
            ("Push and pull", "Tension stretches members; compression squeezes them; bending makes a beam curve."),
            ("Stable shapes", "Triangles resist changing shape, so trusses can span gaps with many small members."),
        ],
        "footer": "A fair bridge test measures deflection and failure, not just whether it survives one load.",
    },
    {
        "slug": "31-the-forest-that-shared-its-meals",
        "level": "intermediate",
        "title": "The Forest That Shared Its Meals",
        "subtitle": "Energy flow and nutrient cycling in a food web",
        "kind": "ecosystem",
        "accent": "#69d39b",
        "cards": [
            ("Energy flows one way", "Sunlight enters through producers; energy is spent at each feeding step."),
            ("Many connections", "Food webs link several food chains. A species can be both predator and prey."),
            ("Nature's recyclers", "Decomposers return nutrients from dead matter to soil, where producers can use them again."),
        ],
        "footer": "Removing one species can change every relationship around it.",
    },
    {
        "slug": "32-the-star-that-built-its-own-light",
        "level": "intermediate",
        "title": "The Star That Built Its Own Light",
        "subtitle": "A stellar core, a long wait, and light escaping",
        "kind": "star",
        "accent": "#ffc857",
        "cards": [
            ("Core furnace", "In a star’s core, hydrogen fusion releases energy when gravity compresses the gas."),
            ("Balanced star", "Gravity pulls inward while pressure from hot gas pushes outward; the balance lasts a long time."),
            ("Ancient light", "Energy from the core takes a long time to diffuse outward; light is emitted after many absorptions and re-emissions."),
        ],
        "footer": "A star is powered by nuclear fusion, not by ordinary fire.",
    },
    {
        "slug": "33-the-battery-that-remembered-charge",
        "level": "intermediate",
        "title": "The Battery That Remembered Charge",
        "subtitle": "Electrons, ions, and stored chemical energy",
        "kind": "battery",
        "accent": "#63d5ff",
        "cards": [
            ("Chemical change", "A battery stores chemical energy in reactions that separate charge inside its electrodes."),
            ("Two paths", "Electrons move through the external wire; ions move through the electrolyte to keep charge balanced."),
            ("Recharge", "A charger drives a reverse reaction, moving chemicals back toward their charged state."),
        ],
        "footer": "A battery stores chemical potential, not a pile of electrons waiting inside it.",
    },
    {
        "slug": "30-the-map-of-a-warming-world",
        "level": "advanced",
        "title": "The Map of a Warming World",
        "subtitle": "Energy balance, greenhouse gases, and feedbacks",
        "kind": "climate",
        "accent": "#ff8b70",
        "cards": [
            ("Energy balance", "Earth receives shortwave energy from the Sun and loses longwave energy to space."),
            ("Greenhouse effect", "Gases absorb and re-emit infrared radiation, changing how quickly heat escapes."),
            ("Feedbacks", "Warming can strengthen some responses, such as ice loss and water-vapor effects, while other feedbacks damp change."),
        ],
        "footer": "Weather is an event; climate is the statistics of weather over time.",
    },
    {
        "slug": "31-the-machine-that-learned-from-mistakes",
        "level": "advanced",
        "title": "The Machine That Learned from Mistakes",
        "subtitle": "A practical map of a prediction model",
        "kind": "neural",
        "accent": "#a58bff",
        "cards": [
            ("Inputs", "A model begins with measurable features, such as temperature, wind, and pressure."),
            ("Weights", "Connections combine inputs with adjustable weights; activation functions pass signals onward."),
            ("Learning loop", "Prediction is compared with the target, loss measures error, and backpropagation adjusts weights."),
        ],
        "footer": "Training data, model choice, and human oversight determine whether a forecast is useful.",
    },
    {
        "slug": "32-the-earthquake-beneath-the-mountain",
        "level": "advanced",
        "title": "The Earthquake Beneath the Mountain",
        "subtitle": "Faults, stored stress, seismic waves, and safer towns",
        "kind": "plate",
        "accent": "#f28b55",
        "cards": [
            ["Moving plates", "Earth’s outer shell is broken into plates that move slowly on the mantle beneath them."],
            ["Sudden slip", "Rock can lock while stress builds; an earthquake happens when a fault slips and waves spread."],
            ["Safety", "Building design, early warning, and prepared communities reduce risk even when timing is uncertain."],
        ],
        "footer": "Magnitude describes energy released; intensity describes how shaking feels at a place.",
    },
    {
        "slug": "33-the-edge-of-the-black-hole",
        "level": "advanced",
        "title": "The Edge of the Black Hole",
        "subtitle": "Event horizons, curved spacetime, and an outside observer",
        "kind": "blackhole",
        "accent": "#b68cff",
        "cards": [
            ["Event horizon", "The horizon is a boundary in spacetime, not a solid wall. Escape velocity at the horizon is the speed of light."],
            ["Curved space", "Mass curves spacetime. Near a black hole, clocks and paths depend on gravity and motion."],
            ["Light from outside", "An outside observer can receive light from matter before it crosses the horizon, even though nothing escapes from inside."],
        ],
        "footer": "A stellar-mass black hole can form when a massive star’s core collapses after its fuel is gone.",
    },
]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def rect(x: float, y: float, width: float, height: float, fill: str, stroke: str = "none", radius: int = 0, opacity: float = 1) -> str:
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}" opacity="{opacity}"/>'


def line(x1: float, y1: float, x2: float, y2: float, stroke: str, width: float = 4, dash: str = "") -> str:
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{width}" stroke-linecap="round"{extra}/>'


def circle(cx: float, cy: float, radius: float, fill: str, stroke: str = "none", width: float = 2) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def path(d: str, stroke: str = "none", fill: str = "none", width: float = 4) -> str:
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


def arrow(x1: float, y1: float, x2: float, y2: float, color: str, width: float = 4) -> str:
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 14
    points = [
        x2,
        y2,
        x2 - size * math.cos(angle - math.pi / 6),
        y2 - size * math.sin(angle - math.pi / 6),
        x2 - size * math.cos(angle + math.pi / 6),
        y2 - size * math.sin(angle + math.pi / 6),
    ]
    return line(x1, y1, x2, y2, color, width) + f'<polygon points="{" ".join(f"{point:.1f}" for point in points)}" fill="{color}"/>'


def text(x: float, y: float, value: str, size: int = 24, fill: str = "#e8eef8", weight: int = 500, anchor: str = "start") -> str:
    return f'<text x="{x}" y="{y}" fill="{fill}" font-family="Arial, sans-serif" font-size="{size}px" font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>'


def paragraph(x: float, y: float, value: str, width: int = 32, size: int = 21, fill: str = "#d6e0f0", leading: int = 28) -> str:
    lines = textwrap.wrap(value, width=width)
    return "".join(text(x, y + index * leading, line, size, fill, 400) for index, line in enumerate(lines))


def cloud(x: float, y: float, scale: float = 1.0, fill: str = "#d8e8ff") -> str:
    return "".join([
        circle(x, y, 42 * scale, fill),
        circle(x + 42 * scale, y - 24 * scale, 54 * scale, fill),
        circle(x + 92 * scale, y, 48 * scale, fill),
        rect(x - 42 * scale, y, 134 * scale, 42 * scale, fill, radius=20),
    ])


def water_diagram(accent: str) -> str:
    return "".join([
        circle(180, 250, 56, "#ffd166"), text(180, 330, "Sun energy", 22, "#ffd166", 600, "middle"),
        arrow(360, 360, 560, 300, "#63d5ff"), text(390, 330, "evaporation", 21, "#9de8ff"),
        cloud(650, 230, 1.15), text(650, 345, "condensation", 21, "#d8e8ff", 600, "middle"),
        arrow(790, 330, 820, 485, "#9bcfff"), text(845, 410, "precipitation", 21, "#9de8ff"),
        line(820, 500, 820, 575, "#7bdff8", 5), line(850, 500, 850, 575, "#7bdff8", 5), line(880, 500, 880, 575, "#7bdff8", 5),
        path("M 210 590 C 400 520, 560 640, 760 575 S 1100 540, 1260 610", "#63d5ff", "none", 16),
        text(720, 655, "collection in rivers and soil", 23, "#9de8ff", 600, "middle"),
        arrow(1120, 610, 1160, 360, accent), text(1165, 470, "cycle continues", 21, accent),
    ])


def photosynthesis_diagram(accent: str) -> str:
    return "".join([
        circle(190, 240, 58, "#ffd166"), text(190, 330, "Sunlight", 22, "#ffd166", 600, "middle"),
        arrow(300, 280, 560, 330, "#ffe08a"), text(385, 275, "light energy", 21, "#ffe08a"),
        path("M 690 260 C 530 220, 480 430, 700 500 C 900 450, 860 260, 690 260 Z", "#2d8b68", "#9be7b0", 5),
        path("M 700 280 L 700 500", "#b5f0c0", 5), path("M 700 360 L 590 430 M 700 390 L 820 450 M 700 330 L 800 290", "#b5f0c0", "none", 4),
        text(700, 550, "chloroplasts in a leaf", 22, "#b5f0c0", 600, "middle"),
        arrow(500, 600, 620, 500, "#63d5ff"), text(400, 620, "H2O from roots", 21, "#9de8ff"),
        arrow(1020, 420, 840, 400, "#ff9c9c"), text(1040, 400, "CO2 in", 21, "#ffb3b3"),
        arrow(810, 470, 1010, 560, "#f6d365"), text(1010, 600, "O2 out", 21, "#ffe08a"),
        rect(650, 600, 100, 48, "#8b5a3c", radius=8), text(700, 670, "sugar for growth", 22, "#f6d365", 600, "middle"),
        arrow(760, 500, 735, 600, accent), text(770, 550, "energy", 21, accent),
    ])


def sky_diagram(accent: str) -> str:
    return "".join([
        circle(180, 260, 55, "#ffd166"), text(180, 340, "white sunlight", 22, "#ffd166", 600, "middle"),
        line(235, 260, 1160, 260, "#fff2b0", 4), text(560, 220, "incoming wavelengths", 21, "#fff2b0"),
        circle(620, 260, 13, "#ffffff"), circle(680, 260, 10, "#ffffff"), circle(740, 260, 16, "#ffffff"), circle(800, 260, 11, "#ffffff"),
        text(710, 330, "air molecules scatter light", 21, "#d8e8ff", 600, "middle"),
        arrow(680, 275, 480, 500, "#6fa8ff", 5), arrow(760, 275, 830, 500, "#ff8a70", 5), arrow(820, 275, 1110, 500, "#6fa8ff", 5),
        text(410, 555, "blue reaches eyes", 22, "#9bcfff", 600, "middle"),
        text(830, 555, "red/orange continues", 22, "#ffb3a7", 600, "middle"),
        text(1130, 555, "more path at sunset", 21, "#ffb3a7", 600, "middle"),
        path("M 250 610 C 480 520, 780 640, 1190 545", accent, "none", 5),
        text(700, 650, "our atmosphere redirects sunlight", 22, accent, 600, "middle"),
    ])


def magnet_diagram(accent: str) -> str:
    return "".join([
        rect(470, 270, 250, 105, "#d85c7a", radius=18), rect(720, 270, 250, 105, "#5c8fe0", radius=18),
        text(535, 338, "N", 44, "#ffffff", 800, "middle"), text(905, 338, "S", 44, "#ffffff", 800, "middle"),
        path("M 480 270 C 300 120, 1100 120, 960 270", accent, "none", 5), path("M 500 375 C 320 550, 1030 550, 900 375", accent, "none", 5),
        text(710, 155, "magnetic field lines", 22, "#e7c8ff", 600, "middle"),
        arrow(420, 470, 570, 360, "#ff9c9c"), text(350, 500, "unlike poles attract", 21, "#ffb3b3"),
        arrow(1000, 470, 850, 360, "#9bcfff"), text(1010, 500, "like poles repel", 21, "#9de8ff"),
        rect(270, 600, 210, 70, "#8d9aaa", radius=8), text(375, 645, "iron filings", 21, "#ffffff", 600, "middle"),
        line(300, 680, 450, 680, accent, 3), line(325, 710, 425, 710, accent, 3), line(350, 740, 400, 740, accent, 3),
        text(1010, 650, "coil + current", 22, "#d7c5ff", 600, "middle"), path("M 940 575 C 1030 540, 1130 575, 1200 540", accent, "none", 5), path("M 950 600 C 1040 565, 1140 600, 1210 565", accent, "none", 5),
    ])


def bridge_diagram(accent: str) -> str:
    return "".join([
        line(160, 520, 1240, 520, "#d9e2ef", 18), line(160, 610, 1240, 610, "#6c7b91", 10),
        path("M 260 520 L 350 350 L 440 520 M 440 520 L 530 350 L 620 520 M 620 520 L 710 350 L 800 520 M 800 520 L 890 350 L 980 520 M 980 520 L 1070 350 L 1160 520", accent, "none", 10),
        line(160, 610, 260, 520, "#9aa8bc", 10), line(1160, 520, 1240, 610, "#9aa8bc", 10),
        arrow(700, 190, 700, 320, "#ff8a70", 7), text(700, 170, "load", 25, "#ffb3a7", 700, "middle"),
        arrow(420, 300, 350, 270, "#9de8ff"), text(315, 250, "tension", 21, "#9de8ff", 600, "middle"),
        arrow(980, 300, 1050, 270, "#ffd166"), text(1060, 250, "compression", 21, "#ffe08a", 600, "middle"),
        arrow(350, 540, 280, 590, "#c7a6ff"), text(260, 650, "reaction", 21, "#d7c5ff", 600, "middle"),
        text(700, 690, "triangles keep the frame from racking", 22, accent, 600, "middle"),
    ])


def ecosystem_diagram(accent: str) -> str:
    return "".join([
        circle(180, 220, 48, "#ffd166"), text(180, 290, "Sun", 22, "#ffd166", 600, "middle"),
        rect(520, 270, 90, 170, "#855b3d", radius=12), circle(565, 240, 105, "#4f9d61"), text(565, 465, "producer", 21, "#b5f0c0", 600, "middle"),
        circle(850, 350, 54, "#c99562"), text(850, 455, "herbivore", 21, "#f2c89b", 600, "middle"),
        circle(1120, 235, 64, "#a96b54"), text(1120, 325, "predator", 21, "#f2b39b", 600, "middle"),
        rect(875, 545, 210, 35, "#8b5a3c", radius=16), text(980, 625, "decomposer", 21, "#e4c09b", 600, "middle"),
        arrow(250, 270, 450, 310, "#9de8ff"), text(340, 245, "energy", 21, "#9de8ff", 600, "middle"),
        arrow(650, 350, 790, 350, accent), text(720, 330, "eats", 21, accent, 600, "middle"),
        arrow(910, 315, 1050, 260, accent), text(980, 285, "eats", 21, accent, 600, "middle"),
        arrow(900, 430, 1000, 530, "#c7a6ff"), text(960, 495, "dead matter", 20, "#d7c5ff", 600, "middle"),
        arrow(800, 560, 620, 440, "#c7a6ff"), text(710, 555, "nutrients return", 20, "#d7c5ff", 600, "middle"),
    ])


def star_diagram(accent: str) -> str:
    return "".join([
        circle(700, 365, 190, "#f29f05", "#ffe08a", 5), circle(700, 365, 125, "#ffb52e"), circle(700, 365, 58, "#fff0a6"),
        text(700, 375, "core", 25, "#7a4b00", 800, "middle"),
        arrow(540, 230, 640, 315, "#fff0a6", 5), arrow(860, 230, 760, 315, "#fff0a6", 5), arrow(700, 160, 700, 270, "#fff0a6", 5),
        text(700, 115, "gravity pulls inward", 22, "#ffe08a", 600, "middle"),
        arrow(530, 500, 640, 420, "#ff8a70", 5), arrow(870, 500, 760, 420, "#ff8a70", 5), text(700, 590, "gas pressure pushes outward", 22, "#ffb3a7", 600, "middle"),
        path("M 700 365 C 760 250, 900 240, 930 120", "#fff2b0", "none", 5), path("M 700 365 C 640 250, 500 240, 470 120", "#fff2b0", "none", 5),
        text(700, 85, "energy diffuses; photons re-emitted", 22, "#fff2b0", 600, "middle"),
        text(700, 680, "fusion: hydrogen -> helium + energy", 24, accent, 700, "middle"),
    ])


def battery_diagram(accent: str) -> str:
    return "".join([
        rect(300, 250, 120, 300, "#d66a6a", radius=12), rect(980, 250, 120, 300, "#6aa7d6", radius=12),
        text(360, 435, "anode", 24, "#ffffff", 700, "middle"), text(1040, 435, "cathode", 24, "#ffffff", 700, "middle"),
        rect(420, 250, 560, 300, "#233a59", "#6f9ac4", 4, 0.18), text(700, 400, "electrolyte", 24, "#bfe9ff", 600, "middle"),
        path("M 420 320 C 570 270, 830 370, 980 320", "#8ed8ff", "none", 5), text(700, 290, "ion path", 21, "#bfe9ff", 600, "middle"),
        line(360, 250, 360, 170, "#d8e8ff", 5), line(1040, 250, 1040, 170, "#d8e8ff", 5), line(360, 170, 1040, 170, "#d8e8ff", 5),
        rect(610, 125, 180, 90, "#f0b54b", radius=12), text(700, 180, "load", 27, "#3b2b0c", 800, "middle"),
        arrow(370, 160, 610, 160, "#f6d365"), text(490, 125, "electrons", 21, "#ffe08a", 600, "middle"),
        arrow(790, 160, 1030, 160, "#f6d365"), text(910, 125, "electrons", 21, "#ffe08a", 600, "middle"),
        text(700, 650, "oxidation + reduction release chemical energy", 23, accent, 600, "middle"),
    ])


def climate_diagram(accent: str) -> str:
    return "".join([
        circle(700, 385, 190, "#2c7fb8", "#bfe9ff", 5), path("M 540 330 C 600 260, 760 240, 850 310 C 780 350, 650 365, 540 330 Z", "#69d39b"),
        path("M 575 450 C 660 500, 800 500, 875 420 C 790 455, 660 450, 575 450 Z", "#69d39b"),
        text(700, 405, "Earth", 30, "#ffffff", 800, "middle"),
        circle(170, 230, 52, "#ffd166"), text(170, 305, "Sun", 22, "#ffd166", 600, "middle"),
        arrow(245, 250, 490, 320, "#ffe08a", 6), text(350, 235, "shortwave in", 21, "#ffe08a", 600, "middle"),
        arrow(1060, 300, 910, 350, "#ff8a70", 6), text(1060, 250, "longwave out", 21, "#ffb3a7", 600, "middle"),
        path("M 470 230 C 650 140, 850 140, 1030 230", "#c7a6ff", "none", 6), text(750, 150, "greenhouse gases", 21, "#d7c5ff", 600, "middle"),
        arrow(520, 520, 350, 600, accent), text(365, 625, "ice / water feedback", 20, accent, 600, "middle"),
        arrow(880, 520, 1050, 600, accent), text(1010, 625, "feedbacks", 20, accent, 600, "middle"),
        text(700, 680, "energy in + energy out define the balance", 23, accent, 600, "middle"),
    ])


def neural_diagram(accent: str) -> str:
    layers = [(300, [260, 370, 480]), (650, [210, 320, 430, 540]), (1000, [300, 430])]
    parts: list[str] = []
    for x1, ys1 in layers[:-1]:
        x2, ys2 = layers[layers.index((x1, ys1)) + 1]
        for y1 in ys1:
            for y2 in ys2:
                parts.append(line(x1 + 25, y1, x2 - 25, y2, "#56658a", 2))
    for x, ys in layers:
        for y in ys:
            parts.append(circle(x, y, 25, accent, "#ffffff", 3))
    parts.extend([
        text(300, 620, "inputs", 23, accent, 700, "middle"), text(650, 620, "weighted connections", 23, accent, 700, "middle"), text(1000, 620, "prediction", 23, accent, 700, "middle"),
        arrow(300, 180, 650, 180, "#9de8ff"), text(475, 155, "features", 21, "#9de8ff", 600, "middle"),
        arrow(650, 180, 1000, 180, "#9de8ff"), text(825, 155, "activation", 21, "#9de8ff", 600, "middle"),
        text(700, 680, "loss -> backpropagation -> updated weights", 23, "#ffb3a7", 600, "middle"),
    ])
    return "".join(parts)


def plate_diagram(accent: str) -> str:
    return "".join([
        path("M 180 270 L 650 220 L 700 500 L 230 540 Z", "#7b91b5", "#d9e2ef", 4), path("M 700 220 L 1190 280 L 1150 520 L 700 500 Z", "#9b6d58", "#f0c1a0", 4),
        path("M 700 500 C 600 590, 540 610, 430 650", accent, "none", 8), path("M 700 500 C 820 590, 900 610, 1010 650", accent, "none", 8),
        line(700, 220, 700, 500, "#ff8a70", 6, "12 10"), text(700, 575, "fault", 22, "#ffb3a7", 700, "middle"),
        arrow(500, 180, 500, 270, "#ff8a70", 6), text(500, 155, "plate motion", 21, "#ffb3a7", 600, "middle"),
        arrow(900, 180, 900, 280, "#ff8a70", 6), text(900, 155, "plate motion", 21, "#ffb3a7", 600, "middle"),
        circle(700, 400, 18, "#ff8a70"), text(700, 370, "stress", 21, "#ffb3a7", 600, "middle"),
        path("M 700 400 C 620 340, 470 350, 300 280", "#f6d365", "none", 4), path("M 700 400 C 780 340, 930 350, 1100 280", "#f6d365", "none", 4),
        text(700, 680, "sudden slip sends seismic waves through the crust", 23, accent, 600, "middle"),
    ])


def blackhole_diagram(accent: str) -> str:
    return "".join([
        circle(700, 365, 178, "#090b16", accent, 6), circle(700, 365, 220, "none", "#7bd66b", 3),
        path("M 450 365 C 520 230, 880 230, 950 365 C 880 500, 520 500, 450 365 Z", "#ff8a70", "none", 18),
        path("M 450 365 C 520 300, 880 300, 950 365", "#ffd166", "none", 6),
        text(700, 375, "black hole", 30, "#ffffff", 800, "middle"), text(700, 150, "accretion disk", 22, "#ffb3a7", 600, "middle"),
        text(700, 600, "event horizon: boundary, not a solid wall", 22, "#b5f0c0", 600, "middle"),
        arrow(350, 250, 480, 320, "#9de8ff", 5), text(300, 220, "infalling matter", 21, "#9de8ff", 600, "middle"),
        arrow(1100, 250, 930, 320, "#9de8ff", 5), text(1130, 220, "light from outside", 21, "#9de8ff", 600, "middle"),
        text(700, 680, "gravity curves paths and clocks near the boundary", 23, accent, 600, "middle"),
    ])


def diagram(kind: str, accent: str) -> str:
    return {
        "water": water_diagram,
        "photosynthesis": photosynthesis_diagram,
        "sky": sky_diagram,
        "magnet": magnet_diagram,
        "bridge": bridge_diagram,
        "ecosystem": ecosystem_diagram,
        "star": star_diagram,
        "battery": battery_diagram,
        "climate": climate_diagram,
        "neural": neural_diagram,
        "plate": plate_diagram,
        "blackhole": blackhole_diagram,
    }.get(kind, lambda _accent: circle(700, 380, 120, accent))(accent)


def card(x: float, heading: str, body: str, accent: str) -> str:
    return "".join([
        rect(x, 715, 400, 205, "#131e32", "#2c3d5e", 16),
        rect(x, 715, 400, 8, accent, radius=4),
        text(x + 28, 770, heading, 25, accent, 700),
        paragraph(x + 28, 810, body, 31, 20, "#d6e0f0", 27),
    ])


def render(topic: dict[str, object]) -> str:
    accent = str(topic["accent"])
    title = str(topic["title"])
    subtitle = str(topic["subtitle"])
    cards = topic["cards"]
    assert isinstance(cards, list)
    body = [
        rect(0, 0, WIDTH, HEIGHT, "#0b1220"),
        rect(40, 40, WIDTH - 80, HEIGHT - 80, "#0f192b", "#263754", 24),
        text(80, 105, title, 42, "#f4f7fb", 800),
        text(82, 145, subtitle, 23, accent, 500),
        line(80, 170, 1320, 170, "#263754", 2),
        diagram(str(topic["kind"]), accent),
    ]
    for index, item in enumerate(cards):
        if isinstance(item, list) and len(item) == 2:
            heading, text_body = item
        else:
            heading, text_body = item
        body.append(card(80 + index * 420, str(heading), str(text_body), accent))
    body.append(text(80, 965, str(topic["footer"]), 20, "#9fb0c9", 500))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}"><title>{esc(title)}</title><desc>{esc(subtitle)}</desc>{"".join(body)}</svg>'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args()
    written = 0
    for topic in TOPICS:
        slug = str(topic["slug"])
        if args.only and not any(selector in slug for selector in args.only):
            continue
        target = args.output / str(topic["level"]) / f"{slug}.svg"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        temporary.write_text(render(topic), encoding="utf-8")
        temporary.replace(target)
        written += 1
        print(f"made {target.relative_to(ROOT)}")
    print(f"generated {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
