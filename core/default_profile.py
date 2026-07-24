# -*- coding: utf-8 -*-
"""
Domyślna, ogólna treść przykładowego profilu firmowego (kategorie, lokalizacje,
szablon, temat). Żyje w `core`, a nie w `ui`, bo `core/database.py` musi to
wstawić do bazy przy pierwszym uruchomieniu (`init_db`) - `core` nie powinno
zależeć od `ui`. `ui/styles.py` re-eksportuje te same stałe dla wygody
istniejących importów w warstwie interfejsu.

Uwaga: stopka szablonu celowo używa zmiennych {company_name}/{company_address}/
{company_phone}/{company_email}/{company_website} zamiast danych na stałe -
podstawiają się automatycznie z ustawień profilu (zakładka Ustawienia -> Dane
firmy), więc każdy nowy profil ma neutralny, bezpieczny do pokazania szablon.
"""

DEFAULT_QUERIES = """Gastronomie
Restaurants
Restaurant
Imbiss
Döner Imbiss
Asia Imbiss
Grillimbiss
Currywurst Imbiss
Pommes Bude
Pizzeria
Schnellrestaurant
Fast Food Restaurant
Burger Restaurant
Bistro
Café
Cafés
Bar
Kneipe
Food Truck
Catering Unternehmen
Partyservice
Kantine
Betriebskantine
Mensa
Vereinsgaststätte
Hotels
Krankenhäuser
Kliniken
Pflegeheime
Bäckereien
Konditoreien
Eisdielen
Brauereien
Systemgastronomie
Hausverwaltungen
Wohnungsbaugesellschaften
Immobilienverwaltungen
Industriebetriebe
Schulen
Kindergärten
Einzelhandel
Facility-Management-Unternehmen
Gebäudemanagement-Unternehmen
Gewerbliche Vermieter
Bürokomplex
Lebensmittelproduktion"""

DEFAULT_LOCATIONS = """Berlin
Potsdam
Oranienburg
Falkensee
Bernau bei Berlin
Eberswalde
Königs Wusterhausen
Schwedt/Oder
Fürstenwalde/Spree
Neuruppin
Blankenfelde-Mahlow
Hennigsdorf
Hohen Neuendorf
Ludwigsfelde
Werder (Havel)
Teltow
Wandlitz
Kleinmachnow
Panketal
Zossen
Neuenhagen bei Berlin
Hoppegarten
Nauen
Rüdersdorf bei Berlin
Strausberg
Schönefeld
Erkner
Wildau
Michendorf
Nuthetal"""

DEFAULT_TEMPLATE = """{{Sehr geehrte Damen und Herren der {firma}|Guten Tag, liebes Team der {firma}|Hallo werte Kolleginnen und Kollegen von {firma}}},

{{Als regionaler Dienstleister unterstützen wir Unternehmen in der Region bei der professionellen Umsetzung unserer Leistungen|Als Fachbetrieb helfen wir Unternehmen in der Region bei der zuverlässigen Umsetzung unserer Leistungen}}, um Qualität und Zuverlässigkeit für Ihren Betrieb sicherzustellen.

Da dies für Ihren Betrieb von zentraler Bedeutung sein könnte, möchten wir anfragen, ob Sie derzeit oder bei zukünftigen Projekten Bedarf an unseren Dienstleistungen haben. Zu unserem Leistungsspektrum gehören:

    - Beispiel-Dienstleistung 1
    - Beispiel-Dienstleistung 2
    - Beispiel-Dienstleistung 3
    - Beispiel-Dienstleistung 4

Wir bieten Neukunden aktuell einen Kennenlernrabatt von 20 % auf den ersten Auftrag!

{{Falls Sie Interesse an einer Zusammenarbeit haben, würden wir uns über eine kurze Rückmeldung z. B. mit Angabe der Telefonnummer des zuständigen Ansprechpartners freuen.|Bei Interesse freuen wir uns über eine kurze Rückmeldung mit einer Kontaktmöglichkeit für weitere Details.}} Alternativ können Sie uns auch gerne direkt telefonisch kontaktieren.

Falls kein Bedarf an einer Kontaktaufnahme besteht, ignorieren Sie diese E-Mail bitte – Sie werden keine weiteren Nachrichten von uns erhalten.

Mit freundlichen Grüßen

{company_name}
{company_address}

Telefon: {company_phone}
E-Mail: {company_email}
Web: {company_website}"""

DEFAULT_SUBJECT = (
    "{{Anfrage zur Zusammenarbeit mit {firma}"
    "|Unverbindliches Angebot für {firma}"
    "|Kontaktanfrage: Zusammenarbeit mit {firma}}}"
)

DEFAULT_PROFILE_NAME = "Domyślny"
