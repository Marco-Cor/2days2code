import gmaps
import sqlite3
from datetime import datetime
from ipywidgets.embed import embed_minimal_html

### Non funziona senza account google cloud platform

def crea_collegamento_db(nome_db):
	# Connessione al database
	connessione_db = sqlite3.connect(nome_db)
	cursore_db = connessione_db.cursor()
	return connessione_db, cursore_db

def crea_tabella(nome_db, cursore_db):
	# Crea la tabella solo se non esiste
	cursore_db.execute('CREATE TABLE IF NOT EXISTS bidone(id INTEGER PRIMARY KEY, via VARCHAR(255), cap VARCHAR(255), tipo_rifiuto VARCHAR(255), perc_riempimento INTEGER, data_riempimento DATE, ora_riempimento TIME, lat INTEGER, lon INTEGER)')

def seleziona_bidoni_in_ordine_di_vicinanza(in_lat, in_lon):
	lat_corrente = in_lat
	lon_corrente = in_lon
	id_presi = [] # gli id dei bidoni da ignorare nelle query
	coordinate_ordinate = [(lat_corrente, lon_corrente)]
	i = 0
	query = "SELECT COUNT(via) FROM bidone WHERE perc_riempimento > " + str(max_riempimento)
	# ^ restituisce il numero dei bidoni considerati pieni
	cursore_db.execute(query)
	n_bidoni = cursore_db.fetchall()[0][0]
	str_id_presi = "()" # queste è la stringa da mettere nella query per i bidoni da ignorare nelle query
	# 'AND ... NOT IN' accetta solo il formato (...,...,...)

	while(i<n_bidoni):
		# il risultato della query cambia ogni volta che la i aumenta dato che lat_corrente e lon_corrente cambiano
		query = "SELECT id, lat, lon FROM bidone WHERE perc_riempimento > " + str(max_riempimento) + " AND id NOT IN " + str_id_presi + " ORDER BY ((lat - " + str(lat_corrente) + ")*(lat - " + str(lat_corrente) + ")) + ((lon - " + str(lon_corrente) + ")*(lon - " + str(lon_corrente) + ")) ASC"
		cursore_db.execute(query)
		dati = cursore_db.fetchall()

		id_presi.append(dati[0][0])
		str_id_presi = "("
		for el in id_presi:
			str_id_presi = str_id_presi + str(el) + ","
		str_id_presi = str_id_presi[:-1] # elimino ultimo carattere (",")
		str_id_presi = str_id_presi + ")"

		lat_corrente = dati[0][1]
		lon_corrente = dati[0][2]
		coordinate_ordinate.append((dati[0][1], dati[0][2]))
		i = i + 1

	return coordinate_ordinate

nome_db = 'dati_bidoni.db'
connessione_db, cursore_db = crea_collegamento_db(nome_db)
crea_tabella(nome_db, cursore_db)

max_riempimento = 80
apikey = "AIzaSyDiiVl2rjRt2eLLDTDNHdBzyKEivsSF2cQ"

partenza = (41.268, 16.4101)
punti_bidoni = seleziona_bidoni_in_ordine_di_vicinanza(partenza[0], partenza[1])
destinazione = punti_bidoni[len(punti_bidoni)-1]

ora = datetime.now()

gmaps.configure(api_key=apikey)

fig = gmaps.figure()
layer = gmaps.directions.Directions(partenza, destinazione, waypoints=punti_bidoni, optimize_waypoints=True, mode="car", api_key=apikey, departure_time=ora)
fig.add_layer(layer)
embed_minimal_html('percorso_gmaps.html', views=[fig])

connessione_db.close()