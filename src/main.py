import flet as ft
import flet_permission_handler as fph
import yt_dlp
import os
from pathlib import Path
import asyncio
import subprocess
import platform


class YouTubeDownloader:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "MAGIC"
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.theme_mode = ft.ThemeMode.DARK
        
        # State
        self.downloading = False
        self.download_path = self.get_download_path()
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
                # width=200,
            ),
            # padding=10
        )
        
        self.init_ui()

    def get_download_path(self):
        try:
            if 'ANDROID_STORAGE' in os.environ:
                if hasattr(self, 'audio_only') and self.audio_only.value:
                    return "/storage/emulated/0/Music"
                return "/storage/emulated/0/Movies"
        except Exception as e:
            print(f"Error detecting Android path: {e}")
    
        # Fallback per desktop
        return str(Path.home() / "Downloads")

    def open_folder(self, e):
        """Open the download folder using the default file explorer"""
        if platform.system() == "Windows":
            os.startfile(self.download_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", self.download_path])
        else:  # Linux and others
            subprocess.run(["xdg-open", self.download_path])

    def init_ui(self):
    
        self.progress_column = ft.Column(
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        self.status_text = ft.Text(
            "",
            text_align=ft.TextAlign.CENTER,
            width=400
        )


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
            icon=ft.Icons.FOLDER_OPEN_SHARP,
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

        self.progress_column = ft.Column(spacing=10)

        # Layout
        self.page.add(
            ft.Column(
                [
                    ft.Text("MAGIC", size=30, weight=ft.FontWeight.BOLD),
                    self.urls_input,
                    self.audio_only,
                    directory_row,
                    self.progress_column,
                    ft.Column(
                        [
                            self.download_button,
                            self.status_text,
                            self.open_folder_button
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
            width=400 
        )
        progress = ft.ProgressBar(value=0, visible=True, width=400)
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
            text.value = f"Extraction file..."
            self.open_folder_button.visible = True  # Show the button after first successful download
            self.page.update()

    async def download_url(self, url: str):
        text, progress_bar = self.create_progress_bar(url)
        self.progress_bars[url] = (text, progress_bar)
        self.page.update()


        ydl_opts = {
            'format': 'bestaudio/best' if self.audio_only.value else 'bestvideo+bestaudio/best',
            'outtmpl': f"{self.download_path}/%(title)s.%(ext)s",
            'progress_hooks': [lambda d: self.update_progress(url, d)],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }] if self.audio_only.value else [],
            'keepvideo': False,
            # 'tmpdir': f"{self.download_path}",  # Set temporary directory
            'verbose': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'writethumbnail': False,
            'updatetime': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.get_event_loop().run_in_executor(None, lambda: ydl.download([url]))
            self.has_downloads = True
            text.value = "Extraction completed!"
        except Exception as e:
            text.value = f"Error with {url}: {str(e)}"
            self.page.update()

    async def download_all(self, urls):
        try:
            tasks = [self.download_url(url) for url in urls]
            await asyncio.gather(*tasks)
            self.status_text.value = "All downloads completed!"
        except Exception as e:
            self.status_text.value = f"General error: {str(e)}"
        finally:
            self.downloading = False
            self.download_button.disabled = False
            self.page.update()

    async def start_downloads(self, e):
        if self.downloading:
            return
        
        urls = [f"http{url.strip()}" for url in self.urls_input.value.replace(" ", "").split('http') if url.strip()]
        if not urls:
            self.status_text.value = "Please enter at least one valid URL"
            self.page.update()
            return

        self.status_text.value = ""
        self.progress_bars.clear()
        self.progress_column.controls.clear()
        self.page.update()

        self.downloading = True
        self.download_button.disabled = True
        await self.download_all(urls)
        

def main(page: ft.Page):
    ph = fph.PermissionHandler()
    page.overlay.append(ph)
    page.update()

    async def request_permissions():
        await asyncio.sleep(0.5)
        try:
            if platform.release() >= "13":  # Android 13+
                storage_status = ph.request_permission(fph.PermissionType.READ_MEDIA_VIDEO)
            else:
                storage_status = ph.request_permission(fph.PermissionType.MANAGE_EXTERNAL_STORAGE)

            audio_status = ph.request_permission(fph.PermissionType.AUDIO)
            video_status = ph.request_permission(fph.PermissionType.VIDEOS)
            print(f"Permissions: Storage={storage_status}, Audio={audio_status}, Video={video_status}")
        except Exception as e:
            print(f"Permission request failed: {e}")

    page.run_task(request_permissions)
    app = YouTubeDownloader(page)

ft.app(target=main)