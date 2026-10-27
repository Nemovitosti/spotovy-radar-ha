# Spotový Radar pro Home Assistant

Ceny elektřiny v ČR po čtvrthodinách: vyhlášené ceny OTE a predikce na **72 hodin** s pásmem
nejistoty. S tarifem nastaveným na [spotovyradar.cz](https://spotovyradar.cz) i koncová cena
(přirážka obchodníka, distribuce VT/NT, DPH).

Integrace potřebuje API klíč z tarifu **Smart Home**
([spotovyradar.cz/ucet/api](https://spotovyradar.cz/ucet/api)).

## Instalace

### HACS

1. HACS → tři tečky vpravo nahoře → **Vlastní repozitáře** (Custom repositories).
2. Repozitář `https://github.com/Nemovitosti/spotovy-radar-ha`, typ **Integrace**.
3. Najděte **Spotový Radar**, stáhněte a restartujte Home Assistant.

### Ručně

Složku `custom_components/spotovy_radar` zkopírujte do `config/custom_components/` a restartujte
Home Assistant.

## Nastavení

**Nastavení → Zařízení a služby → Přidat integraci → Spotový Radar** a vložte klíč `sr_live_…`.
Klíč zůstane jen v Home Assistantu a posílá se jen v hlavičce `Authorization`. Když ho na webu
zrušíte, Home Assistant požádá o nový.

## Entity

| Entita | Popis |
|---|---|
| Cena elektřiny teď | Koncová cena běžící čtvrthodiny v Kč/kWh (bez tarifu spot). Atribut `forecast` obsahuje celý výhled (`start`, `end`, `price`, `price_p10`, `price_p90`, `official`, `band`) |
| Spotová cena teď | Spot v Kč/kWh bez DPH, atributy `spot_p10`, `spot_p90` |
| Cenové pásmo teď | `negative`, `cheap`, `normal`, `expensive` (semafor jako na webu) |
| Pravděpodobnost záporné ceny | % pro běžící čtvrthodinu |
| Začátek nejlevnějších 3 hodin | Souvislé okno v příštích 24 hodinách s nejnižší průměrnou cenou |
| Vydání predikce | Kdy vyšla použitá predikce (diagnostika) |
| Levná elektřina teď | Zapnuto v pásmu `cheap` nebo `negative` |

Data se stahují každých 5 minut (limit API je 240 dotazů za hodinu na klíč). Běžící čtvrthodina
se posouvá podle hodin, i když je API chvíli nedostupné.

## Příklad: bojler v levných čtvrthodinách

```yaml
automation:
  - alias: "Bojler podle Spotového Radaru"
    triggers:
      - trigger: state
        entity_id: binary_sensor.spotovy_radar_levna_elektrina_ted
    actions:
      - action: "switch.turn_{{ 'on' if trigger.to_state.state == 'on' else 'off' }}"
        target:
          entity_id: switch.bojler
```

Predikce je statistický odhad, ne garantovaná cena. Automatizace nastavte tak, aby výpadek API
nebo chybná predikce nic neohrozily.

---

**English:** Czech electricity prices (OTE day-ahead) in 15-minute intervals plus a 72-hour
forecast from [spotovyradar.cz](https://spotovyradar.cz). Requires an API key (Smart Home plan).
Install via HACS as a custom repository, then add the integration in Settings → Devices & services.

## Vývoj

Testy běží proti skutečnému jádru Home Assistantu s napodobeným API
(`pytest-homeassistant-custom-component`, Python 3.14):

```bash
uv venv && uv pip install -r requirements_test.txt
uv run --no-project pytest
```

GitHub Actions je spouští při každém pushi spolu s kontrolami hassfest a HACS.
