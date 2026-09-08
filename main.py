"""
Multi-Platform Auto-Scraper for YouTube, TikTok, and Instagram (Indonesia) - GUI Version
"""

import sys
import os
import threading
import platform
import subprocess
import customtkinter as ctk

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

class PrintRedirector:
    """Kelas untuk mengalihkan output print() terminal ke TextBox GUI."""
    def __init__(self, textbox):
        self.textbox = textbox

    def write(self, text):
        self.textbox.insert(ctk.END, text)
        self.textbox.see(ctk.END)

    def flush(self):
        pass

class ScraperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto-Scraper Influencer & Afiliator")
        self.geometry("650x750")
        self.resizable(False, False)

        # Main Frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # Judul
        self.title_label = ctk.CTkLabel(self.main_frame, text="🌟 Scraper Influencer & Afiliator 🌟", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=(10, 20))

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

        # Container agar tata letak tidak berantakan saat input baru muncul
        self.category_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.category_container.pack(fill="x", padx=20, pady=(0, 15))

        categories = list(NICHES.keys())
        categories.extend(["Semua Kategori", "Lainnya"]) # Menambahkan opsi Lainnya

        self.category_var = ctk.StringVar(value=categories[0])
        self.category_menu = ctk.CTkOptionMenu(
            self.category_container,
            values=categories,
            variable=self.category_var,
            command=self.toggle_custom_category # Panggil fungsi saat opsi diubah
        )
        self.category_menu.pack(fill="x")

        # Input kustom disiapkan tapi tidak di-pack (disembunyikan) secara default
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

        # Tombol Buka Folder Hasil (TAMBAHKAN KODE INI)
        self.open_folder_btn = ctk.CTkButton(
            self.main_frame,
            text="📁 Buka Folder Hasil",
            command=self.open_export_folder,
            fg_color="#2b7a4b", # Warna hijau agar berbeda dengan tombol mulai
            hover_color="#1e5434"
        )
        self.open_folder_btn.pack(fill="x", padx=20, pady=(0, 10))

        # Log Output (TextBox)
        self.log_box = ctk.CTkTextbox(self.main_frame, height=200, state="normal")
        self.log_box.pack(fill="both", padx=20, pady=(10, 20), expand=True)

        # Redirect stdout (print) ke TextBox
        sys.stdout = PrintRedirector(self.log_box)

    def toggle_custom_category(self, choice):
        """Menampilkan atau menyembunyikan input teks kategori."""
        if choice == "Lainnya":
            self.custom_category_entry.pack(fill="x", pady=(10, 0))
        else:
            self.custom_category_entry.pack_forget()

    def open_export_folder(self):
        """Membuka folder 'exports' di file manager bawaan OS."""
        # Menentukan path folder exports
        base_dir = os.path.dirname(os.path.abspath(__file__))
        export_path = os.path.join(base_dir, "exports")

        # Jika folder belum ada (karena belum pernah scrape), buat foldernya
        if not os.path.exists(export_path):
            os.makedirs(export_path)

        # Buka folder sesuai Sistem Operasi
        try:
            if platform.system() == "Windows":
                os.startfile(export_path)
            elif platform.system() == "Darwin": # macOS
                subprocess.Popen(["open", export_path])
            else: # Linux (termasuk Arch/CachyOS)
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

            # --- Parsing Input ---
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

            # ❌ HAPUS DUA BARIS DI BAWAH INI KARENA AKAN MERUSAK LOGIKA INPUT CUSTOM:
            cat_choice = self.category_var.get()
            selected_categories = list(NICHES.keys()) if cat_choice == "Semua Kategori" else [cat_choice]

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
            # Mengembalikan status tombol saat selesai/error
            self.start_btn.configure(state="normal", text="🚀 Mulai Scraping")

if __name__ == "__main__":
    app = ScraperApp()
    app.mainloop()