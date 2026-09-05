# Meal Planner — App per la pianificazione settimanale dei pasti

Breve applicazione per creare, copiare e gestire pasti su base giornaliera/settimanale.

**Stato**: work-in-progress

## Contenuti di questo README

- **Descrizione**: cosa fa il progetto
- **Tecnologie**: stack usato e struttura del repository
- **Avvio rapido**: comandi per eseguire il progetto (Docker)
- **Sviluppo locale**: istruzioni per sviluppare localmente
- **API**: endpoints principali e loro utilizzo
- **Schema DB**: tabelle e campi
- **Contribuire**: come contribuire
- **Licenza e contatti**

## Tecnologie e struttura

- Backend: Flask + SQLAlchemy (cartella [src/brackend](src/brackend))
- Frontend: React (cartella [src/frontend](src/frontend))
- Container: `Dockerfile`, `docker-compose.yml`
- Backend deps: `src/brackend/requirements.txt`
- Frontend deps: `src/frontend/package.json`

Struttura principale del repository:

- [src/brackend](src/brackend)
- [src/frontend](src/frontend)

## Avvio rapido (Docker)

Le istruzioni seguenti avviano l'applicazione usando Docker Compose.

```bash
docker-compose up --build
```

Questo costruisce e avvia i servizi definiti in `docker-compose.yml`.

## Sviluppo locale (senza Docker)

### Backend (Flask + SQLAlchemy)

Per lo sviluppo locale usare un ambiente virtuale Python e installare le dipendenze elencate in `src/brackend/requirements.txt`.

Le variabili d'ambiente principali sono ad esempio `FLASK_APP`, `FLASK_ENV`, `DATABASE_URL` e `SECRET_KEY` — configurare `DATABASE_URL` per puntare a PostgreSQL quando si usa il container DB definito in `docker-compose.yml`.

Per eseguire l'app Flask in sviluppo usare il comando standard `flask run` o l'equivalente del tuo runner, assicurandosi che le variabili d'ambiente siano impostate correttamente.

### Frontend (React)

Nel frontend, nella cartella `src/frontend`, si trovano i sorgenti React. Installare le dipendenze e avviare il dev server con gli strumenti standard (`npm`/`pnpm`/`yarn`) a seconda del file `package.json` presente.

## API — Endpoints principali

Esempi di endpoints disponibili (descrizione breve):

- `POST /login` — body: `{ username, password }` (password hash + salt). Restituisce JWT valido 1 anno.
- `POST /meal` — crea o sovrascrive un record meal (body: oggetto meal).
- `POST /copy_meals?source_from=<gg/mm/aaaa>&source_to=<gg/mm/aaaa>&dest_from=<gg/mm/aaaa>&dest_to=<gg/mm/aaaa>` — copia pasti da intervallo sorgente a destinazione.
- `DELETE /meal?id=<meal_id>` — elimina un meal per `id`.
- `GET /meal?id=<meal_id>` — recupera un singolo meal.
- `GET /meals?from=<gg/mm/aaaa>&to=<gg/mm/aaaa>&type=<type_id>` — lista meals in un intervallo (filtro `type` opzionale).
- `GET /types` — restituisce i tipi di pasto disponibili.

Nota: adattare nomi e percorsi se il router nell'app differisce.


## Schema del database (concetti e mapping consigliati per PostgreSQL)

Usiamo PostgreSQL come database centrale, istanziato tramite `docker-compose`. Di seguito le scelte progettuali e le raccomandazioni sul mapping dei tipi e delle relazioni (testo descrittivo, senza codice):

- Identificatori: usare UUID (UUIDv4) per le chiavi primarie delle tabelle principali (`users`, `roles`, `groups`, `types`, `meals`) per semplicità di integrazione tra servizi e sicurezza.
- Tipi colonna:
	- `username`: stringa limitata (es. 40 caratteri) e univoca.
	- `password`: salvare solo l'hash (lunghezza adeguata, es. 128 caratteri) insieme a salt; non salvare mai la password in chiaro.
	- `email`: stringa con vincolo di unicità opzionale.
	- `avatar_url`: stringa (URL), opzionale.
	- `name` per `roles`, `groups`, `types`: stringhe limitate (es. 30 caratteri) e spesso univoche.
	- `datetime` per `meals`: campo timestamp con timezone, indicizzato per ricerche per intervallo (es. week range queries).
	- `description` per `meals`: campo testo (variabile) per note dettagliate.

- Relazioni:
	- `users` ↔ `groups` e `users` ↔ `roles`: implementare molte-a-molte tramite tabelle di associazione.
	- `meals` ha riferimenti a `types` e `users` tramite foreign key.

- Tipi specifici PostgreSQL consigliati:
	- `UUID` nativo per chiavi primarie.
	- `ARRAY(TEXT)` oppure `JSONB` per campi come `privileges` (se si vuole una lista di stringhe con query avanzate, `ARRAY` è semplice; `JSONB` è più flessibile per strutture complesse).
	- `TIMESTAMP WITH TIME ZONE` per date/ore.

- Indici e performance:
	- Aggiungere indici su colonne usate per filtri/ordinamenti frequenti (`datetime`, `user_id`, `type_id`).
	- Considerare indici parziali se necessario (es. per stati spesso filtrati).

- Migrazioni:
	- Usare uno strumento di migrazione (es. Alembic) per gestire evoluzioni dello schema in ambienti diversi.

- Sicurezza e privacy:
	- Non salvare dati sensibili in chiaro; usare hash per password, proteggere la stringa di connessione al DB e le chiavi JWT tramite variabili d'ambiente e secret manager quando possibile.



## Configurazione

- Variabili d'ambiente suggerite:
	- `DATABASE_URL` — stringa di connessione al DB
	- `SECRET_KEY` — chiave per JWT
	- `PORT` — porta del server



