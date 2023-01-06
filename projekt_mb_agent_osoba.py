#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import spade
import time
from datetime import datetime

roboti = ["markob1@localhost", "markob2@localhost"]


def printSVremenom(stringZaIspis):
    print(f"{datetime.now().strftime('(%H:%M:%S)')} - {stringZaIspis}")


class OsobaAgent(spade.agent.Agent):
    class GlavnoPonasanje(spade.behaviour.CyclicBehaviour):
        async def on_start(self):
            print("Osoba pocinje s radom.")

        async def run(self):
            zadana_akcija = input("Zadaj akciju: ")
            if zadana_akcija == "exit":
                self.kill()
                return
            msg = spade.message.Message(to="markob1@localhost")
            msg.set_metadata("zadana_akcija", "akcija za robote")
            msg.body = f"{zadana_akcija}"
            await self.send(msg)
            msg.to = "markob2@localhost"
            await self.send(msg)
            printSVremenom(f"AGENT OSOBA: Akcija poslana robotima.")

        async def on_end(self):
            await self.agent.stop()

    async def setup(self):
        radOkruzja = self.GlavnoPonasanje()
        self.add_behaviour(radOkruzja)


if __name__ == "__main__":
    osoba = OsobaAgent("markob3@localhost", "markob3")
    future_osoba = osoba.start()
    future_osoba.result()

    while osoba.is_alive():
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            osoba.stop()
            print("\nZaustavljam agenta...")

    spade.quit_spade()
