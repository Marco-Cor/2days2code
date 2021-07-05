import kivy
import random
import sqlite3
from plyer import gps
import urllib.request
from kivy.app import App
from kivy.lang import Builder
from kivy.utils import platform
from kivy.uix.label import Label
from kivy.uix.popup import Popup
# import plotly.graph_objects as go <- solo se voglio usare plotly
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.garden.mapview import MapMarkerPopup
from kivy.uix.screenmanager import ScreenManager, Screen

if platform == "android":
	from android.permissions import request_permissions, Permission
	request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION], Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE)
# ^ Se mi trovo su android chiedo all utente il permesso per leggere i dati forniti dal gps e i permessi per leggere e scrivere file
# se non lo chiedo non posso fare molte cose

# NB: per poter eseguire il programma senza problemi è necessario aver installato tutte le librerire riportate qui sopra (plyer, kivy, sqlite3, garden)
# Python 3.8.6

####################################################################################################################################### INIZIO DEFINIZIONE SCHERMATE APP

# Manager di screen, gestisce su grafica_azienda.kv tutti gli screen
class WManager(ScreenManager):
	pass

# Necessaria per avvio app
class Bidoni_azienda(App):
	def build(self):
		if controlla_connessione_internet() == True:
			global lat_att, lon_att
			try:
				# controllo se riesco ad accedere al gps
				gps.configure(on_location=self.on_gps_location)
				gps.start()
			except NotImplementedError:
				lat_att, lon_att = alt_gps()
				# ^ Se non riesco (se sono su computer) assegno valori casuali a lat_attuale e lon_attuale solo per testare il programma
				# visualizzare_popup("Errore", Err_no_gps())
				# ^ se sono su dispositivo mobile questo rigo non deve essere commentato e 'return grafica' deve stare alla fine del try
			return grafica
		else:
			visualizzare_popup("Errore", Err_no_internet())
			# Se non c'è connessione ad internet non carico la grafica dell'app in quanto sarebbe impossibile far funzionare i pulsanti
			# (al momento non sto usando un database presente nella rete, la connessione ad internet non è necessaria per il funzionamento dell'app)
	def on_gps_location(self, **kwargs):
		global lat_att, lon_att
		# Qua non ci posso arrivare se non sono su un dispositivo mobile, plyer non lo permette
		lat_att = kwargs['lat']
		lon_att = kwargs['lon']

# Schermata principale
class Main(Screen):
	def prendi_testo_btn_cliccato(self, btn):
		# btn contiene tutti i dati del pulsante cliccato dello screen "Main", su grafica_azienda.kv viene passato come self
		global rifiuto_selezionato
		rifiuto_selezionato = str(btn.text)

# Schermata contenente il risultato della query generata da trova_bidone() in una tabella
class bidoni(Screen):
	def on_enter(self):
		self.ids.lista_bidoni_disp.clear_widgets()
		# ^ elimina precedenti dati inseriti nel BoxLayout "lista_bidoni_disp"
		try:
			bidoni_disp = trova_bidone(rifiuto_selezionato)
			if bidoni_disp == []:
				self.lbl = Label(text="Non ci sono bidoni da svuotare")
				self.ids.lista_bidoni_disp.add_widget(self.lbl)
			else:
				for riga in bidoni_disp:
					self.lbl_bidone = Label(text=riga[0])
					self.ids.lista_bidoni_disp.add_widget(self.lbl_bidone)
					self.lbl_riempimento = Label(text=determina_stato_bidone(riga[1]))
					self.ids.lista_bidoni_disp.add_widget(self.lbl_riempimento)
		except:
			visualizzare_popup("Errore", Err_no_bidoni_pieni())
			# ^ Per qualsiasi tipo di errore nella lettura dei dati

# Schermata contenente il percorso ottimale scritto da seguire per raccogliere solo i bidoni pieni
class Percorso(Screen):
	def on_enter(self):
		self.id_percorso.text = calcolare_percorso(lat_att, lon_att)

# Schermata contenente una mappa (OpenStreetMap)
class MappaPercorso(Screen):
	def on_enter(self):
		# Inserisco tanti marker quanti bidoni pieni sulla mappa
		marker = MapMarkerPopup(lat=lat_att, lon=lon_att, source="marker_pos_att.png") # Marker rosso della posizione attuale
		marker.add_widget(Button(text="Posizione\nattuale", background_color=(.05, .05, .05, .5)))
		self.ids.id_mappa.add_widget(marker)
		coordinate_bidoni_pieni = ottieni_dati_bidone()
		for riga in coordinate_bidoni_pieni:
			str_dati_bidone = "id: " + str(riga[0]) + "\n" + riga[3] + "\n" + riga[1] + "\n" + determina_stato_bidone(riga[2])
			marker = MapMarkerPopup(lat=riga[4], lon=riga[5], source="marker_bidone.png") # Marker blu dei bidoni pieni
			marker.add_widget(Button(text=str_dati_bidone, background_color=(.05, .05, .05, .5)))
			self.ids.id_mappa.add_widget(marker)

# Funzioni da passare su "visualizzare_popup", sarebbe il testo (presente su "grafica.kv") che il popup deve contenere
class Err_no_internet(FloatLayout):
	pass

class Err_no_bidoni_pieni(FloatLayout):
	pass

class Err_no_bidoni_vuoti(FloatLayout):
	pass

class Err_no_gps(FloatLayout):
	pass

def visualizzare_popup(titolo_popup,contenuto_popup):
	# Crea una finestra di popup con contenuto variabile
	popup_window = Popup(title=titolo_popup, content=contenuto_popup, size_hint=(None,None), size=(400,500))
	popup_window.open()

####################################################################################################################################### FINE DEFINIZIONE SCHERMATE APP
#################################################################################################################################### INIZIO FUNZIONI GESTIONE DATABASE

def crea_collegamento_db(nome_db):
	# Connessione al database
	connessione_db = sqlite3.connect(nome_db)
	cursore_db = connessione_db.cursor()
	return connessione_db, cursore_db

def crea_tabella(nome_db, cursore_db):
	# Crea la tabella solo se non esiste
	cursore_db.execute('CREATE TABLE IF NOT EXISTS bidone(id INTEGER PRIMARY KEY, via VARCHAR(255), cap VARCHAR(255), tipo_rifiuto VARCHAR(255), perc_riempimento INTEGER, data_riempimento DATE, ora_riempimento TIME, lat INTEGER, lon INTEGER)')

# genera query in base al pulsante cliccato nel "main_screen"
def trova_bidone(rifiuto):
	query = 'SELECT via, perc_riempimento FROM bidone'
	if rifiuto != "tutti i bidoni":
		query = query + " WHERE"
		if rifiuto != "tutti i bidoni\npieni":
			query = query + ' tipo_rifiuto = "' + rifiuto + '" AND '
		query = query + ' perc_riempimento >= "' + str(max_riempimento) + '"'
	cursore_db.execute(query)
	return cursore_db.fetchall()
	
# determina lo stato del bidone al momento della lettura di perc_riempimento da database
def determina_stato_bidone(perc_riempimento):
	# i numeri sono intesi come percentuali di riempimento bidone
	if perc_riempimento >= 0 and perc_riempimento <= 40:
		return "Vuoto"
	elif perc_riempimento >= 41 and perc_riempimento <= 60:
		return "Mezzo pieno"
	elif perc_riempimento >= 61 and perc_riempimento < max_riempimento:
		return "Quasi pieno"
	else:
		return "Pieno"

# Questa funzione calcola il percorso andando dalla posizione attuale al bidone piu vicino, poi dal bidone piu vicino al bidone piu vicino al bidone piu vicino, e così via
# Per determinare quale è il bidone più vicino utilizzo il teorema di pitagora: 'a^2 + b^2 = c^2' e ordino per c^2 in ordine crescente
# Se dovessi fare solo una query che ordini i bidoni pieni dal piu vicino al piu lontano dalla posizione attuale non ottengo un risultato ottimale
# ^ perchè può capitare che il bidone x sia piu lontano dal bidone piu vicino alla pos attuale e che il bidone x+5 sia piu vicino al bidone piu vicino alla pos attuale
# ^ questo perchè ci sono 4 direzioni e il primo bidone può essere verso nord, il secondo verso sud e il terzo verso nord. In questo caso l'ordine deve essere primo, terzo, secondo non primo, secondo, terzo
# ^ anche se il terzo bidone è il piu lontano non posso andare prima a nord, poi a sud e poi a nord, vado a nord e prendo il primo e il secondo e poi vado a sud a prendere il terzo, o viceversa
def calcolare_percorso(in_lat, in_lon):
	percorso = "posizione attuale ->\n"
	lat_corrente = in_lat
	lon_corrente = in_lon
	id_presi = [] # gli id dei bidoni da ignorare nelle query
	#lon_ord = [lon_corrente]
	#lat_ord = [lat_corrente]
	i = 0
	query = "SELECT COUNT(via) FROM bidone WHERE perc_riempimento > " + str(max_riempimento)
	# ^ restituisce il numero dei bidoni considerati pieni
	cursore_db.execute(query)
	n_bidoni = cursore_db.fetchall()[0][0]
	str_id_presi = "()" # queste è la stringa da mettere nella query per i bidoni da ignorare nelle query
	# 'AND ... NOT IN' accetta solo il formato (...,...,...)

	while(i<n_bidoni):
		# il risultato della query cambia ogni volta che la i aumenta dato che lat_corrente e lon_corrente cambiano
		query = "SELECT id, via, lat, lon FROM bidone WHERE perc_riempimento > " + str(max_riempimento) + " AND id NOT IN " + str_id_presi + " ORDER BY ((lat - " + str(lat_corrente) + ")*(lat - " + str(lat_corrente) + ")) + ((lon - " + str(lon_corrente) + ")*(lon - " + str(lon_corrente) + ")) ASC"
		cursore_db.execute(query)
		dati = cursore_db.fetchall()

		id_presi.append(dati[0][0])
		str_id_presi = "("
		for el in id_presi:
			str_id_presi = str_id_presi + str(el) + ","
		str_id_presi = str_id_presi[:-1] # elimino ultimo carattere (",")
		str_id_presi = str_id_presi + ")"

		lat_corrente = dati[0][2]
		lon_corrente = dati[0][3]
		percorso = percorso + dati[0][1] + " ->\n"
		#lon_ord.append(dati[0][3])
		#lat_ord.append(dati[0][2])
		i = i + 1

	percorso = percorso[:-3]
	# print(percorso)
	#genera_mappa_online(lon_ord, lat_ord)
	return percorso

# genera mappa con plotly, levare il commento su linea 11, 168, 169, 194, 195 e 200 per farla funzionare
def genera_mappa_online(lon_ord, lat_ord):
	fig = go.Figure(go.Scattermapbox(
		mode = "markers+lines",
		lon = lon_ord,
		lat = lat_ord,
		marker = {'size': 10}))
	fig.update_layout(
		margin ={'l':0,'t':0,'b':0,'r':0},
		mapbox = {
			'center': {'lon': lon_att, 'lat': lat_att},
			'style': "open-street-map",
			'zoom': 10})
	fig.show()

def ottieni_dati_bidone():
	query = "SELECT id, via, perc_riempimento, tipo_rifiuto, lat, lon FROM bidone WHERE perc_riempimento >= " + str(max_riempimento)
	cursore_db.execute(query)
	return cursore_db.fetchall()

#################################################################################################################################### FINE FUNZIONI GESTIONE DATABASE
########################################################################################################################################## INIZIO FUNZIONI PER DEBUG

# Questa funzione per il momento non è necessaria. Uso un database locale e non mi connetto alla rete per accedere
# Nel caso in cui dovessi connettermi alla rete per accedere ai dati, questa funzione torna utile
# Controlla se riesce a connettersi al sito 'http://google.com' (per vedere se il dispositivo è connesso ad internet), restituisce True se riesce, False se non riesce
def controlla_connessione_internet():
	host = 'http://google.com'
	try:
		urllib.request.urlopen(host)
		return True
	except:
		return False

# dato che non è possibile usare plyer su computer, questa funzione è necessaria per testare l'app su computer
# qua assegno valori casuali a lat_attuale e lon_attuale che non posso determinare in alcun modo se non sono su un dispositivo mobile
def alt_gps():
	lat_attuale = 41.275520
	lon_attuale = 16.417580
	# ^ coordinate di Trani
	return lat_attuale, lon_attuale

# Qua genero dati casuali per riempire il database
# Usando un sensore per ogni bidone si possono ricavare gli stessi dati
# id, tipo_rifiuto e via sarebbero messi manualmente
# perc_riempimento, data_riempimento (assume un valore nel momento in cui tipo_rifiuto raggiunge il 100%) e ora_riempimento (stesso vincolo di data_riempimento)
# ^ saranno determinati dai dati forniti dal sensore del bidone e aggiornati in tempo reale
def popola_db():
	i = 0
	id_via = ["x", "y", "z", "k"]
	tipo_rifiuto = ["carta", "plastica", "vetro", "indifferenziata", "organico"]
	cap = "76125"
	citta = "Trani"
	for item in range(100):
		data = ""
		ora = ""
		y = round(random.uniform(16.376234, 16.419877), 6)
		x = round(random.uniform(41.288474, 41.244088), 6)
		pos = "Via " + random.choice(id_via) + " " + str(random.randint(1, 200)) + ", " + citta
		rifiuto = random.choice(tipo_rifiuto)
		perc_riempimento = random.randint(1, 100)
		if perc_riempimento >= max_riempimento:
			data = str(random.randint(1, 32)) + "/" +  str(random.randint(1, 13)) + "/" + str(random.randint(1999, 2023))
			ora = str(random.randint(0, 24)) + ":" + str(random.randint(0,60)) + ":" + str(random.randint(0, 60))
		cursore_db.execute("INSERT INTO bidone(id, via, cap, tipo_rifiuto, perc_riempimento, data_riempimento, ora_riempimento, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (i, pos, cap, rifiuto, perc_riempimento, data, ora, x, y))
		connessione_db.commit()
		i += 1

############################################################################################################################################# FINE FUNZIONI PER DEBUG

if __name__ == "__main__":
	# Connessione al database
	nome_db = 'dati_bidoni.db'
	connessione_db, cursore_db = crea_collegamento_db(nome_db)
	crea_tabella(nome_db, cursore_db)

	max_riempimento = 90 # % di riempimento oltre la quale il bidone viene considerato pieno
	rifiuto_selezionato = ""
	grafica = Builder.load_file("grafica_azienda.kv")

	try:
		popola_db()
	except:
		pass
	# ^ utile per debug, riempie il database di dati casuali solo se è vuoto
	# Funziona solo al primo avvio, dal secondo in poi va su "except" perchè id=0 esiste già e popola_db inizia con id=0
	# queste 4 righe verranno eliminate nel momento in cui ci sarà un database online con dati aggiornati in tempo reale dai sensori nei cestini

	# .run() richiama la funzione build(self) di Rifiuti(App)	
	Bidoni_azienda().run()

	# Chiude la connessione al db
	connessione_db.close()
