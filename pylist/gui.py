import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser

import PySide6
from PySide6.QtCore import Qt, Signal, Slot, QSize, QObject, QThread
from PySide6.QtGui import QPixmap, QAction, QIcon, QFont
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QLabel,
    QProgressBar,
    QScrollArea,
    QMessageBox,
    QHBoxLayout,
    QMainWindow,
    QSizePolicy,
    QWizardPage,
    QWizard,
    QSplashScreen, QListWidget, QListWidgetItem, QDialog,
)
from pytube import Playlist
from qt_material import apply_stylesheet

from pylist.downloader import (
    download_playlist,
    validate_playlist, pull_genre,
)  # Replace these imports with your actual functions


def get_file(path, filename):
    # Split the path by '/' and remove any empty strings
    split_path = [x for x in path.split("/") if x]
    # Determine the base path
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    alt_base = os.path.join(*os.path.split(base_path)[:-1])
    # Loop through the directory levels in reverse order
    for base in [base_path, alt_base]:
        path_one = os.path.join(base, *split_path, filename)
        path_two = os.path.join(base, split_path[0], filename)
        path_three = os.path.join(base, split_path[1], filename)
        for check_path in [
            path_one,
            path_two,
            path_three,
        ]:  # Check if the file exists in the current path
            if os.path.exists(check_path):
                return check_path
    # Return None if the file was not found
    return None


ASSET_LOCATION = "/pylist/assets/"
IS_WINDOWS_EXE = hasattr(sys, "_MEIPASS")
WIZARD_TITLE = "How to Get a Valid YouTube Playlist URL"
WIZARD_PAGES = [
    {
        "text": "First, head over to YouTube and use the search bar to look for a genre or artist. Avoid searching for specific songs at this stage.",
        "image_path": get_file(ASSET_LOCATION, "page_1.png"),
    },
    {
        "text": "Once the search results are displayed, locate the 'Filter' button at the upper-right corner of the page. \n\nClick it and select 'Playlist' from the dropdown options.",
        "image_path": get_file(ASSET_LOCATION, "page_2.png"),
    },
    {
        "text": "Browse through the filtered results to find a playlist that catches your interest.\n\nEnsure that the thumbnail indicates multiple videos, or look for a listing that includes a 'VIEW FULL PLAYLIST' button. \n\nOpen the playlist you've chosen.",
        "image_path": get_file(ASSET_LOCATION, "page_3.png"),
    },
    {
        "text": "After the playlist page has loaded, you'll see a long list of videos on the right hand side of the page.\n\n You should see the playlist name at the top of this list, click on the 'playlist title' to view the playlist.",
        "image_path": get_file(ASSET_LOCATION, "page_4.png"),
    },
    {
        "text": "You should now be on the playlist's dedicated page. \n\n Verify this by checking if the URL starts with 'youtube.com/playlist?...'. \n\n This is the URL you need.",
        "image_path": get_file(ASSET_LOCATION, "page_5.png"),
    },
]


class HowToPage(QWizardPage):
    def __init__(self, text, image_path):
        super().__init__()
        layout = QVBoxLayout()

        # Create a QLabel for the text
        text_label = QLabel()
        text_label.setText(text)

        # Set the font size and add a border
        text_label.setFont(QFont("Arial", 14))  # Adjust the font size as needed
        text_label.setStyleSheet("QLabel { border: 2px solid black; padding: 10px; }")

        layout.addWidget(text_label)

        # Create a QLabel for the image
        image = QPixmap(image_path)
        image_label = QLabel()
        image_label.setPixmap(image)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center align the image
        image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(image_label)
        self.setLayout(layout)


class HowToWizard(QWizard):
    def __init__(self, pages, title):
        super().__init__()
        self.setWindowTitle(title)

        for page_info in pages:
            text = page_info["text"]
            image_path = page_info["image_path"]
            self.addPage(HowToPage(text, image_path))


class LoadingModal(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Please wait")
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        layout = QVBoxLayout()
        label = QLabel("Validating playlist...")
        layout.addWidget(label)
        self.setLayout(layout)
        self.setFixedSize(200, 100)
        self.setStyleSheet("QLabel { font-size: 16px; text-align: center; }")


class DownloadWorker(QObject):
    progress = Signal(int, str, str, str, str)
    finished = Signal()

    def __init__(self, playlist, output_folder, genre):
        super().__init__()
        self.playlist = playlist
        self.output_folder = output_folder
        self.genre = genre

    def run(self):
        total_time = 0
        playlist_length = len(self.playlist.video_urls)
        for i, (song_meta, time_taken) in enumerate(
            download_playlist(
                self.playlist,
                self.output_folder,
                genre=self.genre,
                download_indicator_function=self.set_downloading,
            )
        ):
            title = song_meta["title"]
            artist = song_meta["author"]

            total_time += time_taken
            average_time = total_time / (i + 1)
            estimated_remaining = average_time * (playlist_length - (i + 1))

            duration = time.strftime("%M:%S", time.gmtime(time_taken))
            estimated_remaining_str = time.strftime(
                "%M:%S", time.gmtime(estimated_remaining)
            )

            self.progress.emit(i + 1, artist, title, duration, estimated_remaining_str)
            time.sleep(0.1)  # simulate processing time

        self.finished.emit()

    def set_downloading(self, dots=0):
        pass


class App(QMainWindow):
    def __init__(self):
        super(App, self).__init__()
        self.playlist_length = 0
        self.worker_thread = None
        self.download_worker = None
        self.playlist = None
        self.initUI()

    def initUI(self):
        self.output_folder = None
        self.create_menu()
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter Playlist URL")
        self.url_input.editingFinished.connect(self.restore_placeholder)
        url_layout.addWidget(self.url_input)

        self.validate_url_button = QPushButton("Validate URL")
        self.validate_url_button.clicked.connect(self.validate_url)
        url_layout.addWidget(self.validate_url_button)

        layout.addLayout(url_layout)

        self.playlist_title = QLabel()
        self.playlist_title.setVisible(False)
        layout.addWidget(self.playlist_title)

        self.folder_button = QPushButton("Select Output Folder")
        self.folder_button.setEnabled(False)
        self.folder_button.clicked.connect(self.select_folder)
        self.output_location_label = QLabel()
        self.output_location_label.setText("No location selected")
        layout.addWidget(self.folder_button)
        layout.addWidget(self.output_location_label)

        if self.output_location_label == "" or self.output_location_label == "No location selected":
            self.download_button.setEnabled(False)

        self.genre = QLabel()
        self.genre.setText("Genre")
        self.genre_input = QLineEdit()
        self.genre_input.setPlaceholderText("Enter Genre")
        self.genre_input.setEnabled(False)
        layout.addWidget(self.genre)
        layout.addWidget(self.genre_input)

        self.song_list = QListWidget()
        self.song_list.setMinimumHeight(200)
        layout.addWidget(self.song_list)

        self.download_button = QPushButton("Download List")
        self.download_button.clicked.connect(self.start_downloading)
        self.download_button.setEnabled(False)
        layout.addWidget(self.download_button)

        self.progress_label = QLabel("0/0")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        central_widget.setLayout(layout)

        self.setWindowTitle("MP3 Downloader")
        self.setMinimumWidth(500)
        self.show()

    def restore_placeholder(self):
        """Restore placeholder text if input field is empty."""
        if not self.url_input.hasFocus() and not self.url_input.text():
            self.url_input.setPlaceholderText("Enter Playlist URL")

    def validate_url(self):
        url = self.url_input.text()
        if not url:
            return

        # Show the loading modal
        self.loading_modal = LoadingModal(self)
        self.loading_modal.show()

        # Validate playlist (running in the main thread)
        try:
            self.playlist = validate_playlist(url)
            if self.playlist:
                self.playlist_length = len(self.playlist.video_urls)
                self.folder_button.setEnabled(True)
                self.download_button.setEnabled(True)
                self.genre_input.setEnabled(True)
                self.genre_input.setText(pull_genre(self.playlist.title))
                self.playlist_title.setText(self.playlist.title)
                self.playlist_title.setVisible(True)
            else:
                raise Exception("Invalid playlist URL.")
        except Exception as e:
            error_dialog = QMessageBox(self)
            error_dialog.setWindowTitle("Validation Error")
            error_dialog.setText(f"Error: {str(e)}")
            error_dialog.setIcon(QMessageBox.Icon.Warning)
            error_dialog.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            error_dialog.exec()

        self.loading_modal.close()

    def select_folder(self):
        self.output_folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder"
        )
        if self.output_folder and os.path.isdir(self.output_folder):
            self.output_location_label.setText(self.output_folder)
            self.change_all(True)
        else:
            self.output_location_label.setText("Not a valid output folder")

    def change_all(self, status=False):
        self.download_button.setEnabled(status)
        self.genre_input.setEnabled(status)
        self.folder_button.setEnabled(status)
        self.validate_url_button.setEnabled(status)
        self.url_input.setEnabled(status)

    def start_downloading(self):
        if self.validate_location():
            self.change_all(False)
            self.download_button.setText("Downloading...")
            self.download_button.setEnabled(False)

            self.worker_thread = QThread()
            self.download_worker = DownloadWorker(
                self.playlist,
                self.output_folder,
                self.genre_input.text()
            )
            self.download_worker.moveToThread(self.worker_thread)

            self.download_worker.progress.connect(self.update_progress)
            self.download_worker.finished.connect(self.download_finished)
            self.worker_thread.started.connect(self.download_worker.run)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)
            self.worker_thread.finished.connect(self.download_worker.deleteLater)

            self.worker_thread.start()

    def update_progress(self, i, artist, title, duration, estimated_remaining):
        percent = int((i / self.playlist_length) * 100)
        self.progress_bar.setValue(percent)

        new_item = QListWidgetItem(f"{artist} - {title} (Download took: {duration})")
        new_item.setSizeHint(QSize(-1, 20))
        self.song_list.insertItem(0, new_item)
        self.song_list.scrollToItem(new_item)

        self.progress_label.setText(
            f"{i}/{self.playlist_length} (Estimated time remaining: {estimated_remaining})"
        )

    def download_finished(self):
        self.download_button.setText("Download List")
        self.change_all(True)
        self.worker_thread.quit()

    def validate_location(self):
        if self.output_folder is None:
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Save Location Error")
            msg_box.setText("You must first choose a save location. Generally this will be your 'Music' folder")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            return False
        return True

    def create_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        view_menu = menu_bar.addMenu("View")
        about_menu = menu_bar.addMenu("About")

        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close_app)
        file_menu.addAction(close_action)

        what_it_does_action = QAction("What it does", self)
        what_it_does_action.triggered.connect(self.open_what_it_does)
        view_menu.addAction(what_it_does_action)

        find_url_action = QAction("Finding playlist URL", self)
        find_url_action.triggered.connect(self.show_how_to)
        view_menu.addAction(find_url_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self.open_about_dialog)
        about_menu.addAction(about_action)

        website_action = QAction("Website", self)
        website_action.triggered.connect(self.open_github)
        about_menu.addAction(website_action)

    def close_app(self):
        self.close()

    def open_what_it_does(self):
        msg = QMessageBox()
        msg.setWindowTitle("What it does")
        msg.setText(
            "This application enables you to download entire YouTube playlists in MP3 format while also populating the files with as much metadata as possible, including album artwork. \n\n"
            "While streaming services have largely rendered MP3s obsolete for the average listener, they remain essential for DJs and other professionals who need direct access to audio files.\n\nWell-formatted metadata makes it easier to manage your song catalog effectively.\n\nPlease note that this project serves as a proof of concept to demonstrate the technical feasibility of such a service. We do not endorse or encourage the unauthorized distribution of copyrighted material. Always remember to support your favorite artists by purchasing their music legally."
        )
        msg.exec()

    def open_about_dialog(self):
        msg = QMessageBox()
        msg.setWindowTitle("About")
        msg.setText(
            "GUI and CLI interface & metadata injection written by Lewis Morris (lewis.morris@gmail.com)\n\n Libraries Used and Loved: \n\n pytube \n moviepy \n mutagen \n pyside6 \n qt_material"
        )
        msg.exec()

    def open_github(self):
        webbrowser.open("https://github.com/lewis-morris/pylist-grab")

    def show_how_to(self):
        self.wizard = HowToWizard(WIZARD_PAGES, WIZARD_TITLE)
        self.wizard.show()


def show_splash(app: QApplication):
    splash_pix = QPixmap(get_file("pylist/assets/", "splash_small.png"))
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()
    time.sleep(2)
    splash.close()


def gui():
    app = QApplication(sys.argv)
    show_splash(app)

    if IS_WINDOWS_EXE:
        theme_path = get_file("pylist/assets/", "dark_teal.xml")
    else:
        theme_path = "dark_teal.xml"

    icon_path = get_file("pylist/assets/", "icon_256.ico")
    apply_stylesheet(app, theme=theme_path)

    app_icon = QIcon(icon_path)
    app.setWindowIcon(app_icon)

    ex = App()
    ex.setWindowIcon(app_icon)

    sys.exit(app.exec())


if __name__ == "__main__":
    gui()
