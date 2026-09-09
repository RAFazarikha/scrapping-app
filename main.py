"""
Multi-Platform Auto-Scraper for YouTube, TikTok, and Instagram (Indonesia) - GUI Version
"""

import sys
import os
import queue
import threading
import platform
import subprocess
import customtkinter as ctk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import NICHES
from scrapers.youtube_scraper import YouTubeScraper
from scrapers.tiktok_scraper import TikTokScraper
from scrapers.instagram_scraper import InstagramScraper
from exporters.export_data import export_to_excel, export_to_majapahit_laravel
from database.db_manager import DatabaseManager

# Setup tema CustomTkinter
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class LogQueue:
    """Thread-safe log queue for GUI updates."""
    def __init__(self, textbox, interval=100):
        self.textbox = textbox
        self.queue = queue.Queue()
        self.interval = interval
        self._poll()

    def write(self, text):
        self.queue.put(text)

    def flush(self):
        pass

    def _poll(self):
        while True:
            try:
                text = self.queue.get_nowait()
                self.textbox.insert(ctk.END, text)
                self.textbox.see(ctk.END)
            except queue.Empty:
                break
        self.textbox.after(self.interval, self._poll)

class ScraperApp(ctk.CTk):
    DATA_COLUMNS = [
        ("handle", "Username"),
        ("channel_title", "Nama"),
        ("tier", "Tier"),
        ("category", "Kategori"),
        ("subscribers_formatted", "Followers"),
        ("engagement_rate", "ER (%)"),
        ("emails", "Email"),
        ("phone_numbers", "WhatsApp"),
    ]

    def __init__(self):
        super().__init__()

        self.title("Auto-Scraper Influencer & Afiliator")
        self.geometry("900x750")

        self.db = DatabaseManager()

        # Tab utama
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(pady=15, padx=15, fill="both", expand=True)
        self.tabs.add("🚀 Scraping")
        self.tabs.add("▶️ YouTube")
        self.tabs.add("🎵 TikTok")
        self.tabs.add("📸 Instagram")

        self._build_scraping_tab(self.tabs.tab("🚀 Scraping"))
        self._build_data_tab(self.tabs.tab("▶️ YouTube"), "youtube")
        self._build_data_tab(self.tabs.tab("🎵 TikTok"), "tiktok")
        self._build_data_tab(self.tabs.tab("📸 Instagram"), "instagram")

    # ---------- Tab 1: Scraping ----------
    def _build_scraping_tab(self, tab):
        self.main_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True)

        self.title_label = ctk.CTkLabel(self.main_frame, text="🌟 Scraper Influencer & Afiliator 🌟", font=ctk.CTkFont(size=18, weight="bold"))
        self.title_label.pack(pady=(10, 15))

        # Pilihan Platform
        self.platform_label = ctk.CTkLabel(self.main_frame, text="1. Pilih Platform Target:")
        self.platform_label.pack(anchor="w", padx=20)
        self.platform_var = ctk.StringVar(value="YouTube")
        self.platform_menu = ctk.CTkOptionMenu(
            self.main_frame,
            values=["YouTube", "TikTok", "Instagram", "Semua Platform"],
            variable=self.platform_var
        )
        self.platform_menu.pack(fill="x", padx=20, pady=(0, 15))

        # Pilihan Kategori
        self.category_label = ctk.CTkLabel(self.main_frame, text="2. Pilih Kategori:")
        self.category_label.pack(anchor="w", padx=20)

        self.category_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.category_container.pack(fill="x", padx=20, pady=(0, 15))

        categories = list(NICHES.keys())
        categories.extend(["Semua Kategori", "Lainnya"])

        self.category_var = ctk.StringVar(value=categories[0])
        self.category_menu = ctk.CTkOptionMenu(
            self.category_container,
            values=categories,
            variable=self.category_var,
            command=self.toggle_custom_category
        )
        self.category_menu.pack(fill="x")

        self.custom_category_entry = ctk.CTkEntry(self.category_container, placeholder_text="Ketik kategori kustom di sini...")

        # Input Target Data
        self.target_label = ctk.CTkLabel(self.main_frame, text="3. Target jumlah data (Default: 100):")
        self.target_label.pack(anchor="w", padx=20)
        self.target_entry = ctk.CTkEntry(self.main_frame, placeholder_text="100")
        self.target_entry.pack(fill="x", padx=20, pady=(0, 15))

        # Input Minimal Followers
        self.min_f_label = ctk.CTkLabel(self.main_frame, text="4. Minimal Followers (Default: 1000, 0 = semua):")
        self.min_f_label.pack(anchor="w", padx=20)
        self.min_f_entry = ctk.CTkEntry(self.main_frame, placeholder_text="1000")
        self.min_f_entry.pack(fill="x", padx=20, pady=(0, 20))

        # Tombol Mulai
        self.start_btn = ctk.CTkButton(self.main_frame, text="🚀 Mulai Scraping", command=self.start_scraping_thread)
        self.start_btn.pack(fill="x", padx=20, pady=10)

        # Tombol Buka Folder Hasil
        self.open_folder_btn = ctk.CTkButton(
            self.main_frame,
            text="📁 Buka Folder Hasil",
            command=self.open_export_folder,
            fg_color="#2b7a4b",
            hover_color="#1e5434"
        )
        self.open_folder_btn.pack(fill="x", padx=20, pady=(0, 10))

        # Log Output (TextBox)
        self.log_box = ctk.CTkTextbox(self.main_frame, height=200, state="normal")
        self.log_box.pack(fill="both", padx=20, pady=(10, 20), expand=True)

        # Redirect stdout/stderr ke TextBox
        sys.stdout = LogQueue(self.log_box)
        sys.stderr = sys.stdout

    # ---------- Tab 2-4: Data per platform ----------
    def _build_data_tab(self, tab, platform):
        wrapper = ctk.CTkFrame(tab, fg_color="transparent")
        wrapper.pack(fill="both", expand=True)

        # Tombol atas
        btns = ctk.CTkFrame(wrapper, fg_color="transparent")
        btns.pack(fill="x", padx=10, pady=(10, 5))

        # Sort dropdown
        sort_frame = ctk.CTkFrame(btns)
        sort_frame.pack(side="left", padx=(0, 10))
        sort_label = ctk.CTkLabel(sort_frame, text="Urutkan:")
        sort_label.pack(side="left", padx=(0, 5))
        self.sort_var = ctk.StringVar(value="subscribers")
        sort_options = ["subscribers", "channel_title", "engagement_rate", "category"]
        sort_menu = ctk.CTkOptionMenu(sort_frame, values=sort_options, variable=self.sort_var)
        sort_menu.pack(side="left")

        # Direction toggle
        self.reverse_var = ctk.BooleanVar(value=True)  # True = descending (default)
        reverse_btn = ctk.CTkButton(btns, text="↓", width=40, command=self.toggle_sort_direction)
        reverse_btn.pack(side="left", padx=(10, 10))

        # Action buttons
        ctk.CTkButton(btns, text="🔄 Refresh", width=120,
                      command=lambda: self.refresh_table(platform)).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btns, text="📊 Export Excel", width=140,
                      command=lambda: self.export_platform(platform)).pack(side="left")

        info = ctk.CTkLabel(wrapper, text="", anchor="e")
        info.pack(fill="x", padx=10)
        self._info_labels[platform] = info

        # Tabel (ttk.Treeview di dalam frame)
        tree_frame = ctk.CTkFrame(wrapper)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        style = ttk.Style()
        style.theme_use("clam")

        tree = ttk.Treeview(tree_frame, columns=[c for c, _ in self.DATA_COLUMNS], show="headings")
        for col, title in self.DATA_COLUMNS:
            tree.heading(col, text=title, command=lambda c=col: self.sort_table(platform, c))
            tree.column(col, width=140, anchor="w")
        tree.column("emails", width=220)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._trees[platform] = tree

        self.refresh_table(platform)

    _info_labels: dict = {}
    _trees: dict = {}

    def toggle_sort_direction(self):
        current = self.reverse_var.get()
        self.reverse_var.set(not current)
        # Update button text or style if needed

    def sort_table(self, platform, col):
        # Map Treeview columns to db sort columns
        col_map = {
            "handle": "handle",
            "channel_title": "channel_title",
            "tier": "tier",
            "category": "category",
            "subscribers_formatted": "subscribers",
            "engagement_rate": "engagement_rate",
            "emails": "emails",
            "phone_numbers": "phone_numbers"
        }
        sort_col = col_map.get(col, "subscribers")
        self.sort_var.set(sort_col)
        self.refresh_table(platform)

    def refresh_table(self, platform):
        sort_by = getattr(self, "sort_var", ctk.StringVar(value="subscribers")).get()
        reverse = getattr(self, "reverse_var", ctk.BooleanVar(value=True)).get()
        rows = self.db.get_all_influencers(platform=platform, sort_by=sort_by, reverse=reverse)
        tree = self._trees[platform]
        tree.delete(*tree.get_children())
        for r in rows:
            tree.insert("", "end", values=[r.get(c, "") or "" for c, _ in self.DATA_COLUMNS])
        self._info_labels[platform].configure(text=f"{len(rows)} data tersimpan")

    def export_platform(self, platform):
        try:
            path = export_to_excel(platform=platform, min_followers=0)
            if path:
                print(f"✅ Export berhasil: {path}")
                self.open_export_folder()
            else:
                print(f"⚠️ Tidak ada data {platform} untuk diexport.")
        except Exception as e:
            print(f"❌ Gagal export: {e}")

    # ---------- Logika scraping (tidak berubah) ----------
    def toggle_custom_category(self, choice):
        """Menampilkan atau menyembunyikan input teks kategori."""
        if choice == "Lainnya":
            self.custom_category_entry.pack(fill="x", pady=(10, 0))
        else:
            self.custom_category_entry.pack_forget()

    def open_export_folder(self):
        """Membuka folder 'exports' di file manager bawaan OS."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        export_path = os.path.join(base_dir, "exports")

        if not os.path.exists(export_path):
            os.makedirs(export_path)

        try:
            if platform.system() == "Windows":
                os.startfile(export_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", export_path])
            else:
                subprocess.Popen(["xdg-open", export_path])
        except Exception as e:
            print(f"❌ Gagal membuka folder: {e}")

    def start_scraping_thread(self):
        """Menjalankan fungsi utama di thread terpisah agar GUI tidak hang."""
        self.start_btn.configure(state="disabled", text="⏳ Sedang Berjalan...")
        self.log_box.delete("1.0", ctk.END)
        threading.Thread(target=self.run_scraper, daemon=True).start()

    def run_scraper(self):
        try:
            print("=" * 60)
            print("Memulai proses scraping...")

            plat_choice = self.platform_var.get()
            platforms = []
            if plat_choice == "YouTube": platforms = ["youtube"]
            elif plat_choice == "TikTok": platforms = ["tiktok"]
            elif plat_choice == "Instagram": platforms = ["instagram"]
            else: platforms = ["youtube", "tiktok", "instagram"]

            cat_choice = self.category_var.get()
            if cat_choice == "Semua Kategori":
                selected_categories = list(NICHES.keys())
            elif cat_choice == "Lainnya":
                custom_cat = self.custom_category_entry.get().strip()
                if not custom_cat:
                    print("❌ Kategori kustom tidak boleh kosong!")
                    self.start_btn.configure(state="normal", text="🚀 Mulai Scraping")
                    return
                selected_categories = [custom_cat]
            else:
                selected_categories = [cat_choice]

            target_val = self.target_entry.get().strip()
            target_count = int(target_val) if target_val.isdigit() and int(target_val) > 0 else 100

            min_f_val = self.min_f_entry.get().strip()
            min_followers = int(min_f_val) if min_f_val.isdigit() else 1000

            # --- Inisialisasi Scraper ---
            yt_scraper = YouTubeScraper()
            tt_scraper = TikTokScraper()
            ig_scraper = InstagramScraper()
            exported_files = []

            # --- Looping Eksekusi ---
            for plat in platforms:
                for cat in selected_categories:
                    print(f"\n▶️ Menjalankan scraping [{plat.upper()}] - Kategori: [{cat}]...")

                    if plat == "youtube":
                        yt_scraper.scrape_target_count(cat, target_count=target_count)
                    elif plat == "tiktok":
                        tt_scraper.scrape_target_count(cat, target_count=target_count)
                    elif plat == "instagram":
                        ig_scraper.scrape_target_count(cat, target_count=target_count)

                    # Export to Excel
                    excel_path = export_to_excel(platform=plat, category=cat, min_followers=min_followers)
                    if excel_path:
                        exported_files.append(excel_path)

            # Export to Seeder MySQL
            seeder_res = export_to_majapahit_laravel(min_followers=min_followers)

            # --- Hasil Akhir ---
            print("\n" + "=" * 60)
            print("🎉 SEMUA SCRAPING & EXPORT BERHASIL!")
            for f in exported_files:
                print(f" 👉 {f}")
            if seeder_res:
                print(f"\n🏛️ Seeder Laravel:")
                print(f" 👉 SQL: {seeder_res.get('sql')}")
            print("=" * 60)

        except Exception as e:
            print(f"\n❌ TERJADI KESALAHAN: {e}")

        finally:
            # Refresh tabel data & kembalikan tombol
            for plat in ["youtube", "tiktok", "instagram"]:
                self.after(0, self.refresh_table, plat)
            self.start_btn.configure(state="normal", text="🚀 Mulai Scraping")

if __name__ == "__main__":
    app = ScraperApp()
    app.mainloop()
