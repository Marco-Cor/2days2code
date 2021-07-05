import kivy
from kivy.app import App
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.lang import Builder
from plyer import gps
import urllib.request

if platform == "android":
	from android.permissions import request_permissions, Permission
	request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION])
# ^ Se mi trovo su android chiedo all utente il permesso per leggere i dati forniti dal gps
# se non lo chiedo non posso leggerli

### App per testare funzioni plyer

def controlla_connessione_internet():
	host = 'http://google.com'
	try:
		urllib.request.urlopen(host)
		return True
	except:
		return False

# Crea una finestra di popup con contenuto variabile
def visualizzare_popup(titolo_popup,contenuto_popup):
	popup_window = Popup(title=titolo_popup, content=contenuto_popup, size_hint=(None,None), size=(400,400))
	popup_window.open()

class WManager(ScreenManager):
	pass

class Gps(App):
	def build(self):
		if controlla_connessione_internet() == True:
			return grafica
		else:
			visualizzare_popup("Errore", Err_no_internet())

class Main(Screen):
	pass

class Gps_s(Screen):
	def on_enter(self):
		try:
			gps.configure(on_location=self.on_gps_location)
			gps.start()
		except:
			visualizzare_popup("Attivare gps", Err_no_gps())
	def on_gps_location(self, **kwargs):
		lat_attuale = kwargs['lat']
		lon_attuale = kwargs['lon']
		print("latitudine", lat_attuale)
		print("longitudine", lon_attuale)
		self.lat_att.text = lat_attuale
		self.lon_att.text = lon_attuale
		self.pos_att.text = str(lat_attuale) + str(lon_attuale)	

class Err_no_internet(FloatLayout):
	pass

class Err_no_gps(FloatLayout):
	pass

grafica = Builder.load_file("gps.kv")
Gps().run()