**Skapa Gulddata:** Du väljer ut dokument från det sparade JSON-materialet och skapar din lokala gulddata manuellt (där du definierar önskad sluttext eller markerar att dokumentet ska slängas).

4. **Utvärdering & Optimering:** Testar och jämför olika pipelines för extrahering och filtrering mot din gulddata för att hitta den konfiguration som ger bäst score (precision, recall, ROUGE-1).


## 📋 Dataformat för Gulddata

Utvärderingen förväntar sig en mapp som innehåller filer i formatet **JSON Lines (`.jsonl`)**. Varje rad i filen ska vara ett giltigt JSON-objekt som representerar ett dokument med följande struktur:

```json
{
  "id": "se-cc-001",
  "url": "https://example.se",
  "html": "<html><body><h1>Rubrik</h1><p>Manuellt extraherad text...</p></body></html>",
  "text": "Rubrik\n\nManuellt extraherad text..."
}
```

* **`id`**: En unik identifierare för dokumentet (används vid specifik dokumentgranskning).
* **`url`**: Dokumentets ursprungliga webbadress.
* **`html`**: Den fullständiga original-HTML-koden från Common Crawl.
* **`text`**: Det manuellt extraherade facit (guldtexten) som pipelinen utvärderas mot.

---