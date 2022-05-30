"""
A popup window to let user choose whether update or not. If user choose to update, then would download the new version
of software, show the download progress bar, then unzip the downloaded file to override the source code when the download
process is finished.
"""
import logging
import os.path
import re
import subprocess
import sys
import time
from threading import Thread

import wx
from pubsub import pub
import wx.xrc
import pathlib
import func_timeout
import psutil

from pycee.downloader import Downloader

downloader = Downloader()
MODULE_LOGGER = logging.getLogger('tdr.update')


class FrameUI(wx.Frame):
	"""UI class"""
	def __init__(self, parent):
		wx.Frame.__init__(self, parent, id=wx.ID_ANY, title=u"TDR Downloading", pos=wx.DefaultPosition, size=wx.Size(500, 150),
						  style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL)
		self.SetBackgroundColour("white")
		# self.SetSizeHints(wx.DefaultSize, wx.DefaultSize)
		self.SetMaxSize(wx.Size(500, 150))

		bSizer1 = wx.GridBagSizer(3, 3)

		# 进度条
		self.gauge = wx.Gauge(self, range=100, pos=(40, 160), size=(400, 25))
		self.progress = wx.StaticText(self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0)

		bSizer1.Add(self.gauge, (1, 2), (1, 1),  wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, 5)
		bSizer1.Add(self.progress, (1, 3), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, 5)

		self.SetSizer(bSizer1)
		self.Layout()

		self.Centre(wx.BOTH)
		self.Bind(wx.EVT_CLOSE, self.onExit)

	def __del__(self):
		pass

	def start_thread(self):
		pass

	def onExit(self, event):
		MODULE_LOGGER.info("User exit downloading software")
		process = psutil.Process(os.getpid())
		process.kill()


class DownloadDialog(FrameUI):
	def __init__(self, src_file, dst_file, unzip_folder, parent=None):
		"""

		:param src_file: The file that you want to download.
		:param dst_file: The local file path to store the downloaded file.
		:param unzip_folder: The folder which you want to unzip the downloaded file to.
		:param parent: Parent window of current window.
		"""
		FrameUI.__init__(self, parent)
		self.src_file = src_file
		self.dst_file = dst_file
		self.unzip_folder = unzip_folder
		# subscribe to topic 'update', and use update_display() as the listener
		pub.subscribe(self.update_display, 'update')

	def start_thread(self):
		MODULE_LOGGER.info("Start downloading new software")
		self.progress.SetLabelText(f'{0:.2%}')
		DownloadThread(self.src_file, self.dst_file)

	def update_display(self, message):
		"""A listener function that can process message from the topic 'update' """
		self.progress.SetLabelText(f"{message:.2%}")
		self.gauge.SetValue(int(message*100))
		if message == 1:  # 100%, so that we can unzip the downloaded file.
			# The unzip.exe is build from unzip.py as an independent program
			MODULE_LOGGER.info("Download finished. Try to unzip the software")
			subprocess.Popen(f'unzip.exe -src "{str(self.dst_file)}" -dst "{str(self.unzip_folder)}"', shell=True)
			sys.exit()


class DownloadThread(Thread):
	def __init__(self, file, local_file):
		Thread.__init__(self)
		self.local = local_file
		t = Thread(target=downloader.download, args=(file, local_file))
		t.start()
		self.size = os.path.getsize(file)
		self.start()

	def run(self):
		size = 0
		while size < 1:
			time.sleep(1)
			size = os.path.getsize(self.local) / self.size
			wx.CallAfter(self.updatemsg, size)

	def updatemsg(self, count):
		pub.sendMessage('update', message=count)


def check_update(version, source_folder):
	"""Check update for current software

	:param version: Current software version.
	:param source_folder: Where the new version software is.
	:return: str kind of file path or None.
	"""

	# set timeout after 4 seconds because when user use VPN, the intranet speed is very slow, users may feel bad if
	# they wait too long.
	version = float(version)
	source_folder = pathlib.Path(source_folder)
	try:
		# func_timeout.func_set_timeout(3) is a decorator to set timeout for a function. Because
		# when user use VPN to connect to the intranet, The intranet speed may be very slow, we
		# don't want to spend too much time here.
		exist = func_timeout.func_set_timeout(3)(source_folder.exists)()
		if not exist:
			MODULE_LOGGER.warning("Check update failed. Update source folder not exists or you are disconnect with company intranet")
			return None
	except func_timeout.exceptions.FunctionTimedOut:
		MODULE_LOGGER.warning("Check update timeout, check your internet connection.")
		return None

	for file in source_folder.iterdir():
		if file.is_file():
			if 'testdatarecord' in str(file).lower() or 'tdr' in str(file).lower():
				new_version = re.search('\d{1,2}.?\d{1,2}', str(file.name))
				if new_version:
					new_version = float(new_version.group())
					if version < new_version:
						MODULE_LOGGER.info(f"Find new software: {file.name}")
						return file
	MODULE_LOGGER.info("Didn't find new software")
	return None


def mktemp(file, root):
	"""Create a temp folder under 'root', then create a temp file under the folder.

	:param file:
	:param root:
	:return:
	"""
	tmp = pathlib.Path(root).resolve() / 'temp'
	tmp.mkdir(parents=True, exist_ok=True)
	temp_file = pathlib.Path(tmp) / pathlib.Path(file).name
	return temp_file


def main(file, unzip_folder):
	"""

	:param file: The file path, this is the file you want to download
	:param unzip_folder: The folder path that you want to unzip 'file' to this folder to overrider the source code.
	:return:
	"""
	button = wx.MessageBox("""New Version is available! Do you want to update? (The program would restart when it's finished.)\n有新版本可用！是否更新？(更新完成后程序会自动重启)""",
						   'Info', wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
	if button == wx.OK:
		tmp_file = mktemp(file, unzip_folder)
		dlg = DownloadDialog(file, tmp_file, unzip_folder)
		dlg.Show()
		dlg.start_thread()
		return True
	else:
		MODULE_LOGGER.info("User Canceled update.")
		return False


if __name__ == "__main__":
	app = wx.App(False)
	main(r"C:\Users\UNCO9CA\Desktop\MY\software\pycharm-community-2021.1.3.zip", "./")
	app.MainLoop()
