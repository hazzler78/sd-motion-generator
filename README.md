# SD Motion Generator

Ett API för att automatiskt generera kommunala motioner med hjälp av AI och statistik från Kolada.

## 🚀 Funktioner

- Genererar kommunala motioner med hjälp av Grok AI
- Integrerar relevant statistik från Kolada
- Stöd för alla värmländska kommuner
- Automatisk formattering och strukturering av motioner
- Retry-hantering för API-anrop
- Omfattande testsvit

## 📋 Förutsättningar

- Python 3.11+
- x.ai API-nyckel
- Tillgång till Kolada API

## 🛠️ Installation

1. Klona repot:
```bash
git clone https://github.com/hazzler78/sd-motion-generator.git
cd sd-motion-generator
```

2. Skapa och aktivera en virtuell miljö:
```bash
python -m venv venv
# På Windows:
.\venv\Scripts\activate
# På Unix eller MacOS:
source venv/bin/activate
```

3. Installera beroenden:
```bash
pip install -r requirements.txt
```

4. Skapa en `.env` fil i backend-mappen med följande innehåll:
```
XAI_API_KEY=din_api_nyckel_här
```

## 🚦 Starta API:et

```bash
cd backend
uvicorn src.main:app --reload
```

API:et kommer att vara tillgängligt på `http://localhost:8000`

## 📚 API Dokumentation

När API:et är igång, besök:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🧪 Kör tester

```bash
cd backend
pytest tests/test_main.py -v
```

## 📊 API Endpoints

### POST /api/generate-motion

Genererar en motion baserad på ett ämne och valfri statistik.

#### Request Body
```json
{
    "topic": "trygghet",
    "statistics": ["befolkning", "trygghet"],
    "year": 2024,
    "municipality": "karlstad"
}
```

#### Tillgänglig statistik
- befolkning
- trygghet
- ekonomi
- invandring
- arbetslöshet
- socialbidrag
- skattesats

## 👥 Bidra

1. Forka repot
2. Skapa en feature branch (`git checkout -b feature/AmazingFeature`)
3. Committa dina ändringar (`git commit -m 'Add some AmazingFeature'`)
4. Pusha till branchen (`git push origin feature/AmazingFeature`)
5. Öppna en Pull Request

## 📝 Licens

Detta projekt är licensierat under MIT License - se [LICENSE](LICENSE) filen för detaljer. 