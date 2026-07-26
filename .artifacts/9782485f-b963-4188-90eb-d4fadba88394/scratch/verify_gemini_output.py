
import random
import re

class SendWorker:
    SPINTAX_RE = re.compile(r'\{\{((?:(?!\{\{).)*?)\}\}', re.DOTALL)

    @staticmethod
    def sanitize(text):
        # 2. Naprawiamy nadmiarowe klamerki
        text = re.sub(r'\{{3,}', '{{', text)
        text = re.sub(r'\}{3,}', '}}', text)
        return text

    @staticmethod
    def resolve_spintax(text: str) -> str:
        if not text:
            return ""
        iterations = 0
        while "{{" in text and "}}" in text and iterations < 150:
            text = SendWorker.SPINTAX_RE.sub(
                lambda m: random.choice(m.group(1).split('|')),
                text
            )
            iterations += 1
        return text

template = """{{{{Hallo|Guten Tag|Sehr geehrte{{ Damen und Herren| Frau {kontakt}| Herr {kontakt}}}}} {{|{kontakt}}},|Guten {{Morgen|Tag}} {kontakt},}}

{{{{Mein Name ist|Ich melde mich bei Ihnen im Namen von}} {company_name}|{{Wir von}} {company_name} {{sind Ihr zuverlässiger Partner|bieten professionelle Lösungen}} {{für Malerarbeiten und Gebäudereinigung|im Bereich Renovierung und Objektpflege}}}}. {{{{Wir unterstützen|Unser Schwerpunkt liegt darauf, Unternehmen wie}} {firma} {{bei fachgerechten Renovierung von Immobilien sowie der gründlichen Büroreinigung zu entlasten|mit erstklassigen Anstrichen und zuverlässiger Gebäudereinigung zu unterstützen}}|{{Ob {{die professionelle Renovierung von Räumlichkeiten|hochwertige Malerarbeiten}} oder {{eine nachhaltige Gebäudereinigung|die regelmäßige Büroreinigung}} – wir sorgen bei}} {firma} {{for perfekte Ergebnisse|für erstklassige Sauberkeit und Pflege}}.}}

{{{{Hätten Sie Interesse an einer {{kurzen|unverbindlichen}} Zusammenarbeit?|Wäre ein {{kurzer|spontaner}} Austausch dazu für Sie von Interesse?}}|{{Lassen Sie uns gerne dazu austauschen – Sie erreichen {{mich|uns}} direkt unter 015510657291.|Ich freue mich über eine {{kurze|Rückmeldung}} oder Ihren Anruf unter 015510657291.}}}}

{{{{Beste Grüße|Mit freundlichen Grüßen|Herzliche Grüße|Viele Grüße}},|{{Freundliche Grüße aus München,}}}}"""

print("--- RAW TEMPLATE ---")
print(template)

print("\n--- AFTER SANITIZE ---")
sanitized = SendWorker.sanitize(template)
print(sanitized)

print("\n--- RANDOM VARIANTS ---")
for i in range(3):
    print(f"\nVARIANT {i+1}:")
    res = SendWorker.resolve_spintax(sanitized)
    print(res)
    if "{{" in res or "}}" in res:
        print("!! ERROR: Brackets remaining !!")
