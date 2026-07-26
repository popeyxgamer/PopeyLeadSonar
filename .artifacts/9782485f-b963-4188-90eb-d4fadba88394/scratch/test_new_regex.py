
import random
import re

class SendWorker:
    # Nowy regex: szukamy {{, potem czegokolwiek co NIE zawiera {{, aż do najbliższego }}
    # Dzięki temu zmienne typu {firma} nie blokują dopasowania!
    SPINTAX_RE = re.compile(r'\{\{((?:(?!\{\{).)*?)\}\}', re.DOTALL)

    @staticmethod
    def resolve_spintax(text: str) -> str:
        if not text:
            return ""
        iterations = 0
        while "{{" in text and "}}" in text and iterations < 100:
            new_text = SendWorker.SPINTAX_RE.sub(
                lambda m: random.choice(m.group(1).split('|')),
                text
            )
            if new_text == text:
                break
            text = new_text
            iterations += 1
        return text

template = """{{{{Guten Tag|Hallo|Sehr geehrte(r)}} {kontakt}|{{Guten Tag|Hallo}} {{Team|Kollegen}} {{von|bei}} {firma}}},

{{ich {{schreibe Ihnen|wende mich an Sie}} {{im Namen von|seitens}} {company_name}|{{mein Name ist|ich melde mich von}} {company_name}}}. {{Wir {{sind {{spezialisiert auf|Ihr Ansprechpartner für}}|bieten {{professionelle|erstklassige}}}} ASDASD|{{Als Experte für|Im Bereich}} ASDASD {{unterstützen wir {{Unternehmen|Kunden}} wie {firma}|unterstützen wir Sie {{zuverlässig|fachgerecht}}}}}.

{{{{Haben Sie|Besteht bei Ihnen}} {{aktuell|derzeit}} {{Bedarf|Interesse}} {{an einer {{Zusammenarbeit|Partnerschaft}}|an {{unseren Leistungen|einer fachgerechten Unterstützung}}}}?|{{Wir würden uns freuen|Wir hätten Interesse daran}}, {{Sie bei kommenden Projekten zu unterstützen|Ihnen ein {{unverbindliches|maßgeschneidertes}} Angebot zu unterbreiten}}.}}

{{{{Weitere {{Informationen|Details}} und Referenzen|Mehr über unsere Leistungen}} {{finden Sie auf|entnehmen Sie bitte unserer Website}} SDASDAS|{{Gerne können Sie sich auf|Informieren Sie sich gerne unter}} SDASDAS {{ein Bild von unseren Arbeiten machen|weiter über uns informieren}}.}}

{{{{Melden Sie sich {{gerne|jederzeit}} {{unter|telefonisch unter}} 015510657291|{{Treten Sie {{gerne|}} mit uns in Kontakt|Rufen Sie uns {{gerne|jederzeit}} an}} {{unter|}} 015510657291}} {{oder antworten Sie {{direkt|einfach}} na tę wiadomość|für ein {{erstes|kurzes}} Gespräch}}.|{{Über eine {{kurze|rückmeldende}} wiadomość|Über eine Rückantwort}} {{würden wir uns {{sehr|}} freuen|freue ich mich}}.}}

{{{{Beste|Herzliche|Freundliche}} Grüße|{{Mit {{besten|freundlichen}} Grüßen}}}}"""

print("--- Testing with new regex ---")
result = SendWorker.resolve_spintax(template)
print(result)
if "{{" in result or "}}" in result:
    print("\nFAILED: Brackets still exist.")
else:
    print("\nSUCCESS: All spintax resolved correctly!")
