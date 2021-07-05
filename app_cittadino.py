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
from kivy.uix.button import Button
from kivy_garden.mapview import MapView
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

# Manager di screen, gestisce su grafica.kv tutti gli screen
class WManager(ScreenManager):
	pass

# Necessaria per avvio app
class Bidoni_cittadini(App):
	def build(self):
		if controlla_connessione_internet() == True:
			try:
				global lat_att, lon_att
				# controllo se riesco ad accedere al gps
				gps.configure(on_location=self.on_gps_location)
				gps.start()
			except NotImplementedError:
				# Se non riesco (se sono su computer) assegno valori casuali a lat_attuale e lon_attuale solo per testare il programma
				# visualizzare_popup("Errore", Err_no_gps())
				# ^ se sono su dispositivo mobile questo rigo non deve essere commentato e return grafica deve stare nel try
				lat_att, lon_att, pos_att = alt_gps()
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
	def trova_bidone(self, btn):
		# btn contiene tutti i dati del pulsante cliccato dello screen "Main", su grafica.kv viene passato come self
		global rifiuto_selezionato
		rifiuto_selezionato = str(btn.text)

# Schermata contenente tutti i bidoni non pieni presenti nel database
class bidoni(Screen):
	def on_enter(self):
		self.ids.lista_bidoni_disp.clear_widgets()
		# ^ elimina precedenti dati inseriti nel BoxLayout "lista_bidoni_disp"
		try:
			bidoni_disp = ottieni_dati_bidone_ordinati_dal_piu_vicino(lat_att, lon_att, rifiuto_selezionato)
			if bidoni_disp == []:
				self.lbl = Label(text="Tutti i bidoni nelle vicinanze sono pieni")
				self.ids.lista_bidoni_disp.add_widget(self.lbl)
			else:
				for riga in bidoni_disp:
					self.lbl_bidone = Label(text=riga[0])
					self.ids.lista_bidoni_disp.add_widget(self.lbl_bidone)
					self.lbl_riempimento = Label(text=determina_stato_bidone(riga[1]))
					self.ids[riga[0]] = self.lbl_riempimento
					self.ids.lista_bidoni_disp.add_widget(self.lbl_riempimento)
		except:
			visualizzare_popup("Errore", Err_no_bidoni_non_pieni())
			# ^ Per qualsiasi tipo di errore nella lettura dei dati

# Schermata contenente una mappa (OpenStreetMap)
class MappaBidoni(Screen):
	def on_enter(self):
		marker = MapMarkerPopup(lat=lat_att, lon=lon_att, source="marker_pos_att.png") # Marker rosso della posizione attuale
		marker.add_widget(Button(text="Posizione\nattuale", background_color=(.05, .05, .05, .5)))
		self.ids.id_mappa.add_widget(marker)
		coordinate_bidoni_non_pieni = ottieni_dati_bidone()
		for riga in coordinate_bidoni_non_pieni:
			str_dati_bidone = str(riga[0]) + "\n" + riga[1] + "\n" + determina_stato_bidone(riga[2])
			marker = MapMarkerPopup(lat=riga[3], lon=riga[4], source="marker_bidone.png") # Marker blu dei bidoni pieni
			marker.add_widget(Button(text=str_dati_bidone, background_color=(.05, .05, .05, .5)))
			self.ids.id_mappa.add_widget(marker)

### Funzioni da passare su "visualizzare_popup", sarebbe il testo (presente su "grafica.kv") che il popup deve contenere
class Err_no_internet(FloatLayout):
	pass

class Err_no_gps(FloatLayout):
	pass

class Err_no_bidoni_non_pieni(FloatLayout):
	pass
# Crea una finestra di popup con contenuto variabile
def visualizzare_popup(titolo_popup,contenuto_popup):
	popup_window = Popup(title=titolo_popup, content=contenuto_popup, size_hint=(None,None), size=(400,400))
	popup_window.open()

####################################################################################################################################### FINE DEFINIZIONE SCHERMATE APP
#################################################################################################################################### INIZIO FUNZIONI GESTIONE DATABASE

# Si connette al database di nome da specificare quando richiamata
def crea_collegamento_db(nome_db):
	connessione_db = sqlite3.connect(nome_db)
	cursore_db = connessione_db.cursor()
	return connessione_db, cursore_db

def crea_tabella(nome_db, cursore_db):
	# Crea la tabella solo se non esiste
	cursore_db.execute('CREATE TABLE IF NOT EXISTS bidone(id INTEGER PRIMARY KEY, via VARCHAR(255), cap VARCHAR(255), tipo_rifiuto VARCHAR(255), perc_riempimento INTEGER, data_riempimento DATE, ora_riempimento TIME, lat INTEGER, lon INTEGER)')

def ottieni_dati_bidone():
	query = "SELECT tipo_rifiuto, via, perc_riempimento, lat, lon FROM bidone WHERE perc_riempimento < " + str(max_riempimento)
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

# Trova tutti i bidoni non pieni che contengono un tipo di rifiuto da specificare quando richiamata, questi sono in ordine di distanza dalla posizione attuale dell utente
def ottieni_dati_bidone_ordinati_dal_piu_vicino(in_lat, in_lon, rifiuto):
	query = "SELECT via, perc_riempimento FROM bidone"
	if rifiuto != "tutti i bidoni":
		query = query + ' WHERE tipo_rifiuto = "' + rifiuto + '" AND perc_riempimento <= "' + str(max_riempimento) + '"'
	# con teorema di pitagora (a^2 + b^2 = c^2)
	# ordinato per c^2 in ordine crescente
	query = query + " ORDER BY ((lat - " + str(in_lat) + ")*(lat - " + str(in_lat) + ")) + ((lon - " + str(in_lon) + ")*(lon - " + str(in_lon) + ")) ASC"
	cursore_db.execute(query)
	return cursore_db.fetchall()

#################################################################################################################################### FINE FUNZIONI GESTIONE DATABASE
########################################################################################################################################## INIZIO FUNZIONI PER DEBUG

# Questa funzione per il momento non è necessaria. Uso un database locale e non mi connetto alla rete per accedere
# Nel caso in cui dovessi connettermi alla rete per accedere ai dati, questa funzione torna utile
# Controlla se riesce a connettersi al sito 'http://google.com' (solo per debug), restituisce True se riesce, False se non riesce
def controlla_connessione_internet():
	host = 'http://google.com'
	try:
		urllib.request.urlopen(host)
		return True
	except:
		return False

# Qua genero dati casuali per riempire il database
# Usando un sensore per ogni bidone di un determinato luogo si possono ricavare gli stessi dati
# id, tipo_rifiuto e posizione (indica la via) sarebbero messi manualmente
# perc_riempimento (% di riempimento), data_riempimento (assume un valore nel momento in cui tipo_rifiuto raggiunge il 100%) e ora_riempimento (stesso vincolo di data_riempimento)
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

# dato che non è possibile usare il gps di plyer su computer questa funzione è necessaria per testare l'app su computer
# qua assegno valori casuali a lat_attuale e lon_attuale che non posso determinare in alcun modo se non sono su un dispositivo mobile
def alt_gps():
	lat_attuale = 41.275520
	lon_attuale = 16.417580
	# ^ coordinate di Trani
	pos_att = str(lat_attuale) + ", " + str(lon_attuale)
	return lat_attuale, lon_attuale, pos_att

############################################################################################################################################# FINE FUNZIONI PER DEBUG

# Avvio app
if __name__ == "__main__":
	nome_db = 'dati_bidoni.db'
	connessione_db, cursore_db = crea_collegamento_db(nome_db)
	crea_tabella(nome_db, cursore_db)

	max_riempimento = 80 # % di riempimento oltre la quale il bidone viene considerato pieno
	rifiuto_selezionato = ""
	grafica = Builder.load_file("grafica_cittadino.kv")

	try:
		popola_db()
	except:
		pass
	# ^ utile per debug, riempie il database di dati casuali solo se è vuoto
	# Funziona solo al primo avvio, dal secondo in poi va su "except" perchè id=0 esiste già e popola_db inizia con id=0
	# queste 4 righe verranno eliminate nel momento in cui ci sarà un database online con dati aggiornati in tempo reale dai sensori nei cestini

	# .run() richiama la funzione build(self) di Bidoni_cittadini(App)	
	Bidoni_cittadini().run()

	# Chiude la connessione al db
	connessione_db.close()
