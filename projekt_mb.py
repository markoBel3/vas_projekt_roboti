#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import spade
import time
from datetime import datetime, timedelta
import asyncio
from enum import Enum
import spacy
import re
import requests

nlp = spacy.load("en_core_web_md")

roboti = ["markob1@localhost", "markob2@localhost"]


class Lokacija(Enum):
    KUHINJA = 0
    KUPAONA = 1
    SPAVACA_SOBA = 2
    DNEVNI_BORAVAK = 3
    HODNIK = 4


api_key = ""
udaljenosti = [
    # kuhinja, kupaona, spavaca_soba, dnevni_boravak, hodnik
    [0, 2, 2, 1, 1],  # kuhinja
    [2, 0, 1, 2, 1],  # kupaona
    [2, 1, 0, 2, 1],  # spavaca_soba
    [1, 2, 2, 0, 1],  # dnevni_boravak
    [1, 1, 1, 1, 0],  # hodnik
]


class Akcija:
    def __init__(self, radnja, trajanje, mjesto, is_vremenska_akcija):
        self.radnja = radnja
        self.trajanje = trajanje
        self.mjesto = mjesto
        self.is_vremenska_akcija = is_vremenska_akcija


sve_akcije = [
    Akcija("make me a dinner", 45, Lokacija.KUHINJA, False),
    Akcija("make me a breakfast", 25, Lokacija.KUHINJA, False),
    Akcija("make me a spaghetti", 30, Lokacija.KUHINJA, False),
    Akcija("make me a meal", 45, Lokacija.KUHINJA, False),
    Akcija("cook me a meal", 45, Lokacija.KUHINJA, False),
    Akcija("cook dinner", 50, Lokacija.KUHINJA, False),
    Akcija("wash dishes", 20, Lokacija.KUHINJA, False),
    Akcija("clean dishes", 20, Lokacija.KUHINJA, False),
    Akcija("get me a drink", 1, Lokacija.KUHINJA, False),
    Akcija("get me a cola", 1, Lokacija.KUHINJA, False),
    Akcija("get me a beer", 1, Lokacija.KUHINJA, False),
    Akcija("clean kitchen", 30, Lokacija.KUHINJA, False),
    Akcija("clean bathroom", 30, Lokacija.KUPAONA, False),
    Akcija("clean mirror in the bathroom", 7, Lokacija.KUPAONA, False),
    Akcija("wash my clothes", 15, Lokacija.KUPAONA, False),
    Akcija("change sheets", 15, Lokacija.SPAVACA_SOBA, False),
    Akcija("change sheets in the bedroom", 15, Lokacija.SPAVACA_SOBA, False),
    Akcija("make my bed", 3, Lokacija.SPAVACA_SOBA, False),
    Akcija("clean bedroom", 20, Lokacija.SPAVACA_SOBA, False),
    Akcija("vacuum the bedroom", 10, Lokacija.SPAVACA_SOBA, False),
    Akcija("turn on the tv", 1, Lokacija.DNEVNI_BORAVAK, False),
    Akcija("find me a music program", 3, Lokacija.DNEVNI_BORAVAK, False),
    Akcija("clean the living room", 30, Lokacija.DNEVNI_BORAVAK, False),
    Akcija("vacuum the living room", 15, Lokacija.DNEVNI_BORAVAK, False),
    Akcija("clean the holway", 25, Lokacija.HODNIK, False),
    Akcija("clean my shoes", 15, Lokacija.HODNIK, False),
    Akcija("vacuum the holway", 8, Lokacija.HODNIK, False),
]

STANJE_RAD = "STANJE_RAD"
STANJE_MIROVANJE = "STANJE_MIROVANJE"

template_za_dogovor = spade.template.Template()
template_za_dogovor.set_metadata("dogovor", "dogovaranje")


def resetirajAgenta(agent_za_reset):
    agent_za_reset.akcija_za_obradu = None


def printStanje(agent_za_print):
    jid_agenta = agent_za_print.jid
    printSVremenomIAgentom(
        f"Zauzet do {formatirajDatum(agent_za_print.zauzet_do)}", jid_agenta
    )
    printSVremenomIAgentom(
        f"Broj akcija za izvrsit {len(agent_za_print.lista_akcija)}", jid_agenta
    )
    printSVremenomIAgentom(f"trenutna lokacija {agent_za_print.lokacija}", jid_agenta)


def potrebnoVrijeme(obraden_ulaz):
    sadrziMjesto = False
    for ent in obraden_ulaz.ents:
        if ent.label_ == "GPE":
            sadrziMjesto = True
        if sadrziMjesto:
            break
    return sadrziMjesto


def poznataAkcija(obraden_ulaz):
    najslicnija_akcija = None
    slicnost = 0
    for ac in sve_akcije:
        ac_obraden = nlp(ac.radnja)
        slicnost_recenica = obraden_ulaz.similarity(ac_obraden)
        if slicnost_recenica > 0.75 and slicnost_recenica > slicnost:
            najslicnija_akcija = ac
            slicnost = slicnost_recenica
    return najslicnija_akcija


def dohvatiJidRobota(jid_obj):
    return f"{jid_obj.localpart}@{jid_obj.domain}"


def dohvatiDrugogRobota(jid_obj):
    jid_robota = dohvatiJidRobota(jid_obj)
    drugi_robot_lista = list(filter(lambda robot: robot != jid_robota, roboti))
    return drugi_robot_lista[0]


def formatirajDatum(datum):
    return datum.strftime("(%H:%M:%S)")


def printSVremenomIAgentom(stringZaIspis, jid_obj):
    print(
        f"{datetime.now().strftime('(%H:%M:%S)')} - {dohvatiJidRobota(jid_obj)} - {stringZaIspis}"
    )


class RadRobota(spade.behaviour.FSMBehaviour):
    async def on_start(self):
        printSVremenomIAgentom(f"Pocinjem s radom", self.agent.jid)

    async def on_end(self):
        printSVremenomIAgentom(f"Završio u stanju {self.current_state}", self.agent.jid)
        await self.agent.stop()


class Rad(spade.behaviour.State):
    async def run(self):
        trajanje = self.agent.trenutna_obrada.trajanje
        if not self.agent.trenutna_obrada.is_vremenska_akcija:
            self.agent.lokacija = self.agent.trenutna_obrada.mjesto
        formatiran_datum = formatirajDatum(datetime.now() + timedelta(seconds=trajanje))
        printSVremenomIAgentom(
            f"Zapoceo rad sve do {formatiran_datum} na akciji {self.agent.trenutna_obrada.radnja}.",
            self.agent.jid,
        )
        tre_ac = self.agent.trenutna_obrada
        if tre_ac.is_vremenska_akcija:
            obraden_ulaz = nlp(self.agent.trenutna_obrada.radnja)
            mj = ""
            for ent in obraden_ulaz.ents:
                if ent.label_ == "GPE":
                    mj = ent
            open_weather_endpoint = (
                "http://api.openweathermap.org/data/2.5/weather?"
                + "appid="
                + api_key
                + f"&q={mj}"
            )
            response = requests.get(open_weather_endpoint)
            x = response.json()
            if x["cod"] != "404":
                current_temperature = x["main"]["temp"] - 273.15
                vrijeme_opis = x["weather"][0]["description"]
                printSVremenomIAgentom(
                    f"Temperature je: {current_temperature} and opis: {vrijeme_opis}",
                    self.agent.jid,
                )
        else:
            await asyncio.sleep(trajanje)
            printSVremenomIAgentom(
                f"Završio rad na akciji {self.agent.trenutna_obrada.radnja}.",
                self.agent.jid,
            )
        self.agent.trenutna_obrada = None
        self.set_next_state(STANJE_MIROVANJE)


class Mirovanje(spade.behaviour.State):
    async def run(self):
        if len(self.agent.lista_akcija) > 0:
            self.agent.trenutna_obrada = self.agent.lista_akcija.pop(0)
            tr_ukupno = 0
            for ac in self.agent.lista_akcija:
                tr_ukupno += ac.trajanje
            tr_ukupno += self.agent.trenutna_obrada.trajanje
            self.agent.zauzet_do = datetime.now() + timedelta(seconds=tr_ukupno)
            self.set_next_state(STANJE_RAD)
        else:
            await asyncio.sleep(1)
            self.set_next_state(STANJE_MIROVANJE)


class CekajPoruku(spade.behaviour.PeriodicBehaviour):
    async def run(self):
        msg = await self.receive(timeout=100)
        if msg:
            # POCINJE DOGOVOR
            printStanje(self.agent)
            za_obradu = msg.body
            obraden_ulaz = nlp(za_obradu)
            poznata_akcija = poznataAkcija(obraden_ulaz)
            self.agent.akcija_za_obradu = poznata_akcija
            if poznata_akcija or potrebnoVrijeme(obraden_ulaz):
                if poznata_akcija:
                    printSVremenomIAgentom(
                        f"Prepoznata akcija je: {poznata_akcija.radnja} s trajanjem od {poznata_akcija.trajanje} na lokaciji {poznata_akcija.mjesto}",
                        self.agent.jid,
                    )
                    printSVremenomIAgentom(
                        f"Trazim dogovor",
                        self.agent.jid,
                    )
                else:
                    printSVremenomIAgentom(
                        f"Prepoznata vremenska akcija", self.agent.jid
                    )
                    self.agent.akcija_za_obradu = Akcija(za_obradu, 1, None, True)
                    printSVremenomIAgentom(
                        f"Trazim dogovor",
                        self.agent.jid,
                    )
                vrijeme_sad = datetime.now()
                if vrijeme_sad > self.agent.zauzet_do:
                    slobodan_za = 0
                else:
                    slobodan_za = (self.agent.zauzet_do - vrijeme_sad).seconds
                res = re.search("(\d)", dohvatiJidRobota(self.agent.jid))
                id = res.groups()[0]
                if not self.agent.akcija_za_obradu.is_vremenska_akcija:
                    udaljenost = udaljenosti[self.agent.lokacija.value][
                        self.agent.akcija_za_obradu.mjesto.value
                    ]
                else:
                    udaljenost = 0
                printSVremenomIAgentom(
                    f"Moj slobodan_za: {slobodan_za}", self.agent.jid
                )
                printSVremenomIAgentom(f"Moj id: {id}", self.agent.jid)
                printSVremenomIAgentom(f"Moja udaljenost: {udaljenost}", self.agent.jid)
                msg = spade.message.Message(to=dohvatiDrugogRobota(self.agent.jid))
                msg.set_metadata("dogovor", "dogovaranje")
                msg.body = f"{id}{udaljenost}{slobodan_za}"
                await asyncio.sleep(1)
                await self.send(msg)
                msg_rec = await self.receive(timeout=10)
                printSVremenomIAgentom("Primio podatak", self.agent.jid)
                sl_drugi = int(msg_rec.body[2:])
                id_drugi = int(msg_rec.body[0])
                udaljenost_drugi = int(msg_rec.body[1])
                printSVremenomIAgentom(f"Drugi slobodan_za: {sl_drugi}", self.agent.jid)
                printSVremenomIAgentom(f"Drugi id: {id_drugi}", self.agent.jid)
                printSVremenomIAgentom(
                    f"Drugi udaljenost: {udaljenost_drugi}", self.agent.jid
                )
                if sl_drugi > slobodan_za:
                    printSVremenomIAgentom(
                        f"Uzimam akciju: {self.agent.akcija_za_obradu.radnja}",
                        self.agent.jid,
                    )
                    self.agent.lista_akcija.append(self.agent.akcija_za_obradu)
                    resetirajAgenta(self.agent)
                elif sl_drugi < slobodan_za:
                    printSVremenomIAgentom("Drugi ce uzeti.", self.agent.jid)
                else:
                    if self.agent.akcija_za_obradu.is_vremenska_akcija:
                        if int(id) < id_drugi:
                            printSVremenomIAgentom(
                                f"Uzimam akciju: {self.agent.akcija_za_obradu.radnja}",
                                self.agent.jid,
                            )
                            self.agent.lista_akcija.append(self.agent.akcija_za_obradu)
                            resetirajAgenta(self.agent)
                        else:
                            printSVremenomIAgentom("Drugi ce uzeti.", self.agent.jid)
                    else:
                        if udaljenost_drugi > udaljenost:
                            printSVremenomIAgentom(
                                f"Uzimam akciju: {self.agent.akcija_za_obradu.radnja}",
                                self.agent.jid,
                            )
                            self.agent.lista_akcija.append(self.agent.akcija_za_obradu)
                            resetirajAgenta(self.agent)
                        elif udaljenost_drugi < udaljenost:
                            printSVremenomIAgentom("Drugi ce uzeti.", self.agent.jid)
                        else:
                            if int(id) < id_drugi:
                                printSVremenomIAgentom(
                                    f"Uzimam akciju: {self.agent.akcija_za_obradu.radnja}",
                                    self.agent.jid,
                                )
                                self.agent.lista_akcija.append(
                                    self.agent.akcija_za_obradu
                                )
                                resetirajAgenta(self.agent)
                            else:
                                printSVremenomIAgentom(
                                    "Drugi ce uzeti.", self.agent.jid
                                )
            else:
                resetirajAgenta(self.agent)
                printSVremenomIAgentom(f"Ne prepoznajem akciju", self.agent.jid)


class RobotAgent(spade.agent.Agent):
    async def setup(self):
        self.zauzet_do = datetime.now()
        self.akcija_za_obradu = None
        self.lokacija = Lokacija.DNEVNI_BORAVAK
        self.lista_akcija = []
        self.trenutna_obrada = None
        radRobota = RadRobota()
        radRobota.add_state(name=STANJE_MIROVANJE, state=Mirovanje(), initial=True)
        radRobota.add_state(name=STANJE_RAD, state=Rad())
        radRobota.add_transition(source=STANJE_MIROVANJE, dest=STANJE_MIROVANJE)
        radRobota.add_transition(source=STANJE_MIROVANJE, dest=STANJE_RAD)
        radRobota.add_transition(source=STANJE_RAD, dest=STANJE_MIROVANJE)
        self.add_behaviour(radRobota)
        cekanjePoruke = CekajPoruku(period=6)
        self.add_behaviour(cekanjePoruke)


if __name__ == "__main__":
    robot1 = RobotAgent("markob1@localhost", "markob1")
    robot2 = RobotAgent("markob2@localhost", "markob2")
    future_robot1 = robot1.start()
    future_robot1.result()
    future_robot2 = robot2.start()
    future_robot2.result()

    while robot1.is_alive():
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            robot1.stop()
            robot2.stop()
            print("\nZaustavljam robote...")

    spade.quit_spade()
