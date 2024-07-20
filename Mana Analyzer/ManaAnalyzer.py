"""Use permitted under terms of the MIT license.

Copyright (c) 2024 Pascal A. Kirchner

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the “Software”), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
"""

from copy import deepcopy
from random import choice, shuffle
import re


class ManaAnalyzer:
    def __init__(self):
        """Initialisiere alle relevanten Variablen.

       'deck_colors': Color identity (wird später ermittelt)
       'successful': Zählung erfolgreicher Simulationen, in denen alle Farben gezogen wurden.
       'impossible': Zählung der Simulationen, in denen eine Farbe grundsätzlich fehlt (Bsp. nur drei Sümpfe in Rakdos)
       'total_tries': Gesamtzahl der verwendeten Tap-Versuchen über alle Einzelsimulationen hinweg.
       'land_types': Alle möglichen Farbvarianten von Ländern
       'land_base': Im Deck enthaltene Ländervarianten mit Anzahlen (Variante: Anzahl)
       'draw_pile': Im Deck enthaltene Länder. Liste mit einem Eintrag pro Land, um zufällige Länder ziehen zu können.
       'n_of_simulations': Zahl der Einzelsimulationen pro Simulation. Standard: 200k
       'max_tap_tries': Maximale Versuche, um die Länder einer Einzelsimulation optimal zu tappen. Im Regelfall sind
                        durchschnittlich < 5 Versuche notwendig. Allerdings ist die Standardabweichung wohl sehr hoch,
                        da bei Maximalwerten von weniger als 50 deutlich schlechtere Ergebnisse bei ansonsten gleichen
                        Parametern erhalten werden.
        'deck_name': Dateiname mit den Länderzahlen. Die Datei muss 26 Zahlen enthalten, die den einfarbigen,
                     zweifarbigen, dreifarbigen und Any-color entsprechen. Für genaue Reihenfolge siehe 'land_types'
                     Die Einträge in der Datei müssen jeweils durch ein oder mehrere Zeichen aus Leerzeichen, Komma und
                     Strichpunkt getrennt werden.
        """
        self.deck_colors = None
        self.successful = 0
        self.impossible = 0
        self.total_tries = 0
        self.land_types = ["W", "U", "B", "R", "G", "WU", "UB", "BR", "RG", "GW", "WB", "BG", "GU", "UR", "RW",
                           "WUG", "WUB", "UBR", "BRG", "WRG", "WBR", "URG", "WBG", "WUR", "UBG", "WUBRG", "C"]
        self.land_base = dict()
        self.draw_pile = list()
        self.n_of_simulations = 200000
        self.max_tap_tries = 50
        self.deck_name = "deck.txt"

    def reset(self):
        """Variablen am Anfang einer Simulation zurücksetzen.

        Color identity und die Zählvariablen werden zurückgesetzt, um eine neue Simulation starten zu können.
        """
        self.deck_colors = None
        self.successful = 0
        self.impossible = 0
        self.total_tries = 0

    def load_deck(self):
        """Deck-Datei laden und auswerten.

        Die Datei wird zunächst geöffnet und der Inhalt ausgelesen. Der Inhalt wird an Trennzeichen ('delimiters')
        getrennt. Die erhaltenen Zahlen werden in ein dictionary ('self.land_base') nach einschlägiger Reihenfolge
        den Länder-Arten zugeordnet. Aus diesem dictionary wird außerdem eine Liste ('self.draw_pile') erzeugt, in der
        für jedes Land ein Eintrag enthalten ist (beispielsweise 2 Einträge 'W' für zwei Ebenen) aus der man leicht
        zufällige Länder ziehen kann.
        """
        with open(self.deck_name, "r") as f:
            data = f.readlines()
        delimiters = r',|;| '
        parts = re.split(delimiters, data[0])
        parts_clean = list()
        for part in parts:
            if part != "":
                parts_clean.append(part)
        for index, land_type in enumerate(self.land_types):
            self.land_base[land_type] = int(parts_clean[index])
        for key, value in self.land_base.items():
            for _ in range(value):
                self.draw_pile.append(key)

    def get_color_id(self):
        """Color identity des Decks ermitteln.

        Alle vorhandenen Länder werden betrachtet und alle Farben von allen Ländern (außer Any-color) werden der Color
        id zugerechnet.
        """
        deck_colors = list()
        for land, number in self.land_base.items():
            if land != "WUBRG" and number != 0:
                colors = list(land)
                for color in colors:
                    if color not in deck_colors and color != "C":
                        deck_colors.append(color)
                if len(deck_colors) == 5:
                    break
        self.deck_colors = deck_colors

    def check_availability(self, draws):
        """Für eine Auswahl an Ländern ermitteln, ob überhaupt alle notwendigen Farben vorhanden sind.

        Wenn man drei gleiche Basics hat, muss man nicht versuchen, sie so zu tappen, dass drei verschiedene Farben
        rauskommen. Ebensowenig muss man versuchen, mit zwei Ländern drei Farben zu erzeugen.
        """
        if len(draws) < len(self.deck_colors):
            return False
        all_possible_colors = list()
        for draw in draws:
            all_possible_colors.extend(list(draw))
        for color in self.deck_colors:
            if color not in all_possible_colors:
                self.impossible += 1
                return False
        return True

    def analyze_tap_options(self, draws):
        """Für eine Auswahl an Ländern ermitteln, ob sie im gleichen Zug für alle Deckfarben tappen können.

        'draws' sind die gezogenen Länder. Länder werden zufällig getappt, bis entweder alle Farben erzeugt wurden
        (Simulation erfolgreich -> 'successful' += 1) oder ein Versuchslimit erreicht wurde ('self.max_tap_tries').
        Any-color Länder werden nur für Farben in der Color identity getappt. Die verwendete Zahl an Tap-Versuchen
        wird zu Analyse-Zwecken getrackt.
        """
        for n in range(self.max_tap_tries):
            available = list()
            for draw in draws:
                land_colors = list(draw)
                if len(land_colors) == 5:
                    tapped = choice(self.deck_colors)
                else:
                    tapped = choice(land_colors)
                if tapped not in available:
                    available.append(tapped)
            if len(available) == len(self.deck_colors):
                self.successful += 1
                self.total_tries += n
                return
        self.total_tries += self.max_tap_tries

    def initialize(self):
        """Alles vorbereiten.

        Zählungen zurücksetzen, Deck laden, Color identity ermitteln.
        """
        self.reset()
        self.load_deck()
        self.get_color_id()

    def run_simulation(self, n_of_lands):
        """Durchführen einer kompletten Simulation.

        'n_of_lands' ist die Zahl der Länder, mit der man alle Farben erzielen möchte. Für Initialisierung siehe
        separate Methode. Der Länderstapel wird kopiert und gemischt. Die ersten n Länder des gemischten Stapel werden
        entnommen. Zunächst wird überprüft, ob eine oder mehrere Farben grundsätzlich fehlen oder zu wenige Länder
        gezogen wurden (siehe separate Methode). Falls nicht, wird versucht, die Länder so zu tappen, dass sie alle
        Farben ergeben.

        Die durchschnittlichen Tap-Versuche werden berechnet, wobei nur Einzelsimulationen berücksichtigt werden, die
        nicht als unmöglich galten ('impossible' also zu wenig Länder oder eine notwendige Farbe kann von keinem Land
        erzeugt werden. Daneben wird der Prozentsatz an erfolgreichen Simulationen errechnet. Beide Resultate werden
        auf zwei Nachkommastellen gerundet und ausgegeben.
        """
        self.initialize()
        for _ in range(self.n_of_simulations):
            current_deck = deepcopy(self.draw_pile)
            shuffle(current_deck)
            draws = current_deck[:n_of_lands]
            if self.check_availability(draws):
                self.analyze_tap_options(draws)
        average_tries = round(self.total_tries / (self.n_of_simulations - self.impossible), 2)
        percentage = round(self.successful * 100.0 / self.n_of_simulations, 2)
        print(f"Durchschnitt Tap-Versuche: {average_tries}")
        print(f"Alle Farben vorhanden: {percentage} %")


# Analyse-Tool instanzieren
ma = ManaAnalyzer()
# Simulation durchführen, wobei n (Standard: 3) Länder pro Einzelsimulation gezogen werden.
ma.run_simulation(3)
