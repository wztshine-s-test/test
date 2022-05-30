"""
A popup window to let user choose whether update or not. If user choose to update, then would download the new version
of software, show the download progress bar, then unzip the downloaded file to override the source code when the download
process is finished.
"""
import argparse
import logging
import os
import os.path
import subprocess
import sys
from threading import Thread
import zipfile

import psutil
import wx
import wx.adv
import wx.xrc
from pubsub import pub

EXE = "tdr.exe"


class FrameUI(wx.Frame):
	"""UI class"""

	def __init__(self, parent=None):
		wx.Frame.__init__(self, parent, id=wx.ID_ANY, title=u"TDR Install", pos=wx.DefaultPosition,
						  size=wx.Size(700, 400), style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL)
		self.SetBackgroundColour("white")
		self.SetMaxSize(wx.Size(700, 400))

		layout = wx.GridBagSizer(3, 3)

		self.progress = wx.TextCtrl(self, wx.ID_ANY, "Installing...", (0, 0), size=(685, 370), style=wx.TE_MULTILINE)

		layout.Add(self.progress, (0, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, 5)

		self.SetSizer(layout)
		self.Layout()
		self.Centre(wx.BOTH)

	def start_thread(self):
		pass


class UnzipDialog(FrameUI):
	def __init__(self, parent=None):
		FrameUI.__init__(self, parent)
		pub.subscribe(self.update_display, 'update')

	def start_thread(self):
		UnzipThread()

	def update_display(self, message):
		"""A listener function that can process message from the topic 'update' """
		self.progress.AppendText(f"\nExtracting {message}")
		if message == 'Done':  # unzip finished
			open_program()  #  run the tdr.exe program
			clean_temp(os.path.dirname(params.src))  # remove temp folder
			self.Destroy()
			sys.exit()


class UnzipThread(Thread):
	"""A thread class to unzip file, and publish topic to display extract progress.
	"""

	def __init__(self):
		LOGGER.info("Start extract file...")
		Thread.__init__(self)
		self.start()

	def run(self):
		"""unzip src file to dst folder."""
		try:
			with zipfile.ZipFile(params.src, "r") as zf:
				for info in zf.infolist():
					file_path = info.filename
					file_name = file_path.split('/')[-1]
					# we can't override unzip.exe because we are running it. so we put it at temp folder.
					if file_name == "unzip.exe":
						zf.extract(info, os.path.dirname(params.src))
						continue
					try:
						zf.extract(info, params.dst)
						wx.CallAfter(self.updatemsg, file_path + ' --> ' + params.dst)
					except Exception as e:
						err = f"Unzip Error while processing file: {file_path} with: {e}"
						LOGGER.warning(err)
						wx.CallAfter(self.updatemsg, err)
		except Exception as e:
			err = f"Unzip Failed: {str(e)}"
			LOGGER.error(err)
			wx.CallAfter(self.updatemsg, err)
		finally:
			wx.CallAfter(self.updatemsg, 'Done')
			LOGGER.info("Unzip finished.")

	def updatemsg(self, count):
		pub.sendMessage('update', message=count)


def kill_process(name=None, exclude_pids=None, logger=None):
	"""Default kill all tdr.exe process.

	:param name: The process name. On Win platform you may get it from : Task manager -> Details
	:param exclude_pids: The PID you want to ignore.
	:return:
	"""
	global EXE
	if name is None:
		name = EXE
	for pid in psutil.pids():
		if exclude_pids is not None and pid in exclude_pids:
			continue
		try:
			p = psutil.Process(pid)
			if p.name() == name:
				p.kill()
		except Exception as e:
			if logger:
				logger.error(e)
			else:
				print(e)


def clean_temp(dir):
	file_path = os.path.join(dir, 'unzip.exe')
	LOGGER.info("Trying to delete temp folder.")
	# wait 3s, move ./temp/unzip.exe to ./unzip.exe, then delete the dir.
	cmd = f'TIMEOUT /T 1 /NOBREAK > nul & move /Y "{file_path}" "{os.path.dirname(dir)}" && rd /s /q "{dir}"'
	subprocess.Popen(cmd, shell=True, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


def open_program():
	LOGGER.info(f"Run {EXE}")
	subprocess.Popen(f'{EXE}', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
					 creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


if __name__ == "__main__":
	parse = argparse.ArgumentParser()
	parse.add_argument('-src', type=str, help='file to unzip (Absolute path)', required=True)
	parse.add_argument('-dst', type=str, help='unzip to which folder (Absolute path)', required=True)
	params = parse.parse_args()

	if not os.path.exists('./log'):
		os.mkdir('log')
	logging.basicConfig(filename='./log/update.log', filemode='a', level=logging.INFO)
	LOGGER = logging.getLogger(__name__)

	app = wx.App(False)

	kill_process(logger=LOGGER)

	dlg = UnzipDialog()
	dlg.Show()
	dlg.start_thread()

	app.MainLoop()
