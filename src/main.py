import flet as ft
import yt_dlp
import os
from pathlib import Path
import subprocess
import platform

class YouTubeDownloader:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "MAGIC"
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.theme_mode = ft.ThemeMode.DARK
        
        # Request storage permission on Android
        self.request_storage_permission()
        self.download_path = self.get_android_download_path()
        # State
        self.downloading = False
        self.has_downloads = False  # Track if any downloads completed
        
        # UI Elements
        self.progress_bars = {}
        self.status_text = ft.Text("")
        self.path_container = ft.Container(
            content=ft.Text(
                f"Path: {self.download_path}",
                size=12,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
                text_align=ft.TextAlign.CENTER,
                width=200,
            ),
            padding=10
        )
        
        self.init_ui()
        
        
    def request_storage_permission(self):
        try:
            self.page.client_storage.set("storage_permission_requested", "true")
            storage_permission = self.page.invoke_method("request_storage_permission")
            return storage_permission
        except Exception as e:
            print(f"Error requesting permission: {e}")
            return False

    def get_android_download_path(self):
        return "/storage/emulated/0/Download"
        

    def open_folder(self, e):
        """Open the download folder using the default file explorer"""
        if platform.system() == "Windows":
            os.startfile(self.download_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", self.download_path])
        elif platform.system() == "Linux":
            subprocess.run(["xdg-open", self.download_path])
        else:
            self.page.launch_url(self.download_path)

    def init_ui(self):
        self.urls_input = ft.TextField(
            label="YouTube URL (one per line)",
            width=400,
            multiline=True,
            min_lines=3,
            max_lines=5,
            autofocus=True,
            text_size=14
        )

        self.audio_only = ft.Switch(
            label="Audio only",
            value=True
        )

        self.download_button = ft.ElevatedButton(
            "Download",
            icon=ft.Icons.DOWNLOAD,
            on_click=self.start_downloads
        )

        self.open_folder_button = ft.ElevatedButton(
            "Open Downloads Folder",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self.open_folder,
            visible=False  # Initially hidden until first download
        )

        directory_row = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.FOLDER_OPEN,
                    tooltip="Select folder",
                    on_click=self.pick_directory,
                ),
                self.path_container
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=0
        )

        self.progress_column = ft.Column(
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER  # Centra i contenuti
        )

        # Modifica il layout del status_text
        self.status_text = ft.Text(
            "",
            text_align=ft.TextAlign.CENTER,  # Centra il testo
            width=400  # Larghezza fissa per assicurare il centraggio
        )

        # Layout principale
        self.page.add(
            ft.Column(
                [
                    ft.Text("MAGIC", size=30, weight=ft.FontWeight.BOLD),
                    self.urls_input,
                    self.audio_only,
                    directory_row,
                    self.progress_column,
                    ft.Column(  # Raggruppa i bottoni e il testo di stato
                        [
                            ft.Row(
                                [self.download_button, self.open_folder_button],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=20
                            ),
                            self.status_text,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20
            )
        )

    def pick_directory(self, e):
        def handle_result(e: ft.FilePickerResultEvent):
            if e.path:
                self.download_path = e.path
                self.path_container.content.value = f"Path: {self.download_path}"
                self.page.update()

        file_picker = ft.FilePicker(
            on_result=handle_result
        )
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.get_directory_path()

    def create_progress_bar(self, url: str) -> tuple[ft.Text, ft.ProgressBar]:
        text = ft.Text(
            f"Downloading: {url}",
            text_align=ft.TextAlign.CENTER,
            width=400  # Larghezza fissa per centraggio
        )
        progress = ft.ProgressBar(value=0, visible=True, width=400)  # Larghezza fissa
        column = ft.Column(
            [text, progress],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5
        )
        self.progress_column.controls.append(column)
        return text, progress


    def update_progress(self, url: str, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                progress = (downloaded / total)
                text, progress_bar = self.progress_bars[url]
                progress_bar.value = progress
                text.value = f"Downloading {progress:.1%}: {url}"
                self.page.update()
        elif d['status'] == 'finished':
            text, progress_bar = self.progress_bars[url]
            text.value = f"Completed: {url}"
            self.open_folder_button.visible = True  # Show the button after first successful download
            self.page.update()

    def download_url(self, url: str):
        text, progress_bar = self.create_progress_bar(url)
        self.progress_bars[url] = (text, progress_bar)
        self.page.update()

        ydl_opts = {
            # Se audio only, prendi formato m4a (che non richiede conversione)
            'format': 'm4a/bestaudio[ext=m4a]' if self.audio_only.value else 'best',
            'outtmpl': f"{self.download_path}/%(title)s.%(ext)s",
            'progress_hooks': [lambda d: self.update_progress(url, d)],
            # 'no_warnings': True,
            'postprocessors': [],  # Nessun post-processing
            'keepvideo': True,
            # 'extractor_retries': 3,
            # 'ignoreerrors': True,
            'quiet': False
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self.has_downloads = True
            text.value = f"Completed: {url}"
            self.open_folder_button.visible = True
            self.page.update()
        except Exception as e:
            error_msg = str(e)
            text.value = f"Error with {url}: {error_msg}"
            self.page.update()
            print(f"Download error: {error_msg}")


    def download_all(self, urls):
        try:
            for url in urls:
                self.download_url(url)
            self.status_text.value = "All downloads completed!"
        except Exception as e:
            self.status_text.value = f"General error: {str(e)}"
        finally:
            self.downloading = False
            self.download_button.disabled = False
            self.page.update()

    def start_downloads(self, e):
        if self.downloading:
            return
        
        urls = [url.strip() for url in self.urls_input.value.split('\n') if url.strip()]
        if not urls:
            self.status_text.value = "Please enter at least one valid URL"
            self.page.update()
            return

        # Pulisci i messaggi precedenti
        self.status_text.value = ""
        self.progress_bars.clear()
        self.progress_column.controls.clear()
        self.page.update()

        self.downloading = True
        self.download_button.disabled = True
        self.download_all(urls)

def main(page: ft.Page):
    app = YouTubeDownloader(page)

ft.app(target=main)