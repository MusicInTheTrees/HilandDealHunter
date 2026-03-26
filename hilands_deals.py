"""
Hiland's Cigars - Discount Hunter Application

This application is a specialized web scraper and deal finder for Hiland's Cigars.
It provides a user-friendly GUI to scan the website for cigar deals and analyze discounts.

Features:
1.  **Automated Scraping**:
    *   Discovers brand categories dynamically from the main shop page.
    *   Scans all pages within each brand category using multi-threading for speed.
    *   Avoids redundant page scans and handles redirects.
2.  **Real-Time Results**:
    *   Displays found deals immediately in a sortable table.
    *   Color-coded rows based on discount percentage (e.g., Green for >70% off).
    *   Shows MSRP, Sale Price, and calculated Savings.
3.  **Advanced Filtering**:
    *   Filter by Product Name.
    *   Filter by Minimum and Maximum Discount Percentage.
    *   Filter by Minimum and Maximum Sale Price.
    *   Filter by Stock Status (In Stock Only).
4.  **User Controls**:
    *   Start and Stop scanning at any time.
    *   Export results to CSV.
    *   Double-click rows to open the product page in a web browser.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
import threading
import webbrowser
import re
import urllib.parse
import concurrent.futures
import csv
from tkinter import filedialog

# ==========================================
# Scraper Logic for Hiland's Cigars
# ==========================================
class HilandScraper:
    MAIN_CIGARS_URL = "https://www.hilandscigars.com/shop/cigars/"

    def __init__(self):
        self.seen_links = set()
        self.visited_pages = set()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }

    def stop(self):
        self.stop_event.set()

    def discover_brands(self, status_callback=None):
        """Scrapes the main page to find all brand URLs."""
        brand_urls = []
        if status_callback:
            status_callback(f"Discovering brands from {self.MAIN_CIGARS_URL}...")
        
        try:
            response = requests.get(self.MAIN_CIGARS_URL, headers=self.headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Find links that are likely brand categories (sub-paths of /shop/cigars/)
                for a in soup.select('a[href]'):
                    href = a['href']
                    full_url = urllib.parse.urljoin(self.MAIN_CIGARS_URL, href)
                    
                    # Check if it's a sub-url of the main cigar page, but not the page itself, pagination, or sorting
                    if (full_url.startswith(self.MAIN_CIGARS_URL) and 
                        full_url.rstrip('/') != self.MAIN_CIGARS_URL.rstrip('/') and 
                        '/page/' not in full_url and
                        '?' not in full_url):
                        brand_urls.append(full_url.rstrip('/'))
                
                brand_urls = list(set(brand_urls)) # Remove duplicates
        except Exception as e:
            print(f"Error discovering brands: {e}")
            brand_urls = [self.MAIN_CIGARS_URL] # Fallback to scanning main page if discovery fails
        
        return brand_urls

    def scrape_brand_pages(self, base_url, result_callback):
        """Worker function to scrape all pages of a single brand."""
        found_items = []
        page_num = 1
        consecutive_no_new_items = 0
        
        while True:
            if self.stop_event.is_set():
                break

            # Construct URL
            if page_num == 1:
                url = base_url
            else:
                url = f"{base_url.rstrip('/')}/page/{page_num}/"
            
            # Check if this page has already been scanned (by another thread or alias)
            check_url = url.rstrip('/')
            with self.lock:
                if check_url in self.visited_pages:
                    break
            
            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                
                # Termination checks
                if response.status_code == 404: break
                if response.status_code != 200: break
                if response.url.rstrip('/') != url.rstrip('/'): break # Redirect means done

                # Mark the final URL as visited
                final_url = response.url.rstrip('/')
                with self.lock:
                    if final_url in self.visited_pages:
                        break
                    self.visited_pages.add(final_url)
                    self.visited_pages.add(check_url)

                soup = BeautifulSoup(response.text, 'html.parser')
                products = soup.select('.product, .product-item, .type-product, li.product')
                
                if not products: break
                
                found_new_on_this_page = False
                
                for p in products:
                    if self.stop_event.is_set():
                        break

                    try:
                        # Check Stock Status (WooCommerce uses 'outofstock' class on the product li)
                        classes = p.get('class', [])
                        in_stock = 'outofstock' not in classes

                        # 1. Get Link
                        link_tag = p.select_one('a.woocommerce-LoopProduct-link, .product-image a, a')
                        if not link_tag: continue
                        link = link_tag['href']
                        
                        # Thread-safe check
                        with self.lock:
                            if link in self.seen_links: continue
                            self.seen_links.add(link)
                        
                        found_new_on_this_page = True

                        # 2. Get Name
                        title_tag = p.select_one('.woocommerce-loop-product__title, .product-title, h3, h2')
                        name = title_tag.text.strip() if title_tag else "Unknown Cigar"

                        # 3. Get Price
                        price_tag = p.select_one('.price')
                        if not price_tag: continue

                        del_tag = price_tag.select_one('del')
                        ins_tag = price_tag.select_one('ins')
                        
                        def parse_price(txt):
                            if not txt: return 0.0
                            match = re.search(r'[\d,]+\.\d{2}', txt)
                            if match:
                                return float(match.group().replace(',', ''))
                            return 0.0

                        msrp = 0.0
                        sale_price = 0.0

                        if del_tag and ins_tag:
                            msrp = parse_price(del_tag.text)
                            sale_price = parse_price(ins_tag.text)
                        else:
                            sale_price = parse_price(price_tag.text)
                            msrp = sale_price 

                        discount_pct = 0.0
                        if msrp > sale_price and msrp > 0:
                            discount_pct = ((msrp - sale_price) / msrp) * 100
                            
                        if sale_price > 0:
                            deal = {
                                'name': name,
                                'msrp': msrp,
                                'sale_price': sale_price,
                                'discount_pct': discount_pct,
                                'link': link,
                                'in_stock': in_stock
                            }
                            found_items.append(deal)
                            # Send back to UI immediately
                            if result_callback:
                                result_callback(deal)

                    except Exception:
                        continue 

                # Stop if we haven't found a new item in 2 consecutive pages
                if not found_new_on_this_page:
                    consecutive_no_new_items += 1
                    if consecutive_no_new_items >= 2: break
                else:
                    consecutive_no_new_items = 0

                page_num += 1
                if page_num > 100: break # Safety limit

            except Exception as e:
                # print(f"Error scraping {url}: {e}")
                break
                
        return found_items

# ==========================================
# GUI Application
# ==========================================
class HilandDealApp(tk.Tk):
    SORT_THRESHOLD = 50  # Number of new entries before triggering an auto-sort

    def __init__(self):
        super().__init__()
        self.title("Hiland's Cigars - Discount Hunter")
        self.geometry("1100x700")
        self.configure(bg="#2c2c2c") # Premium dark gray background

        self.scraper = HilandScraper()
        self.products = []
        self.displayed_products = []
        self.sort_counter = 0

        self.setup_ui()

    def setup_ui(self):
        # --- Header ---
        header_frame = tk.Frame(self, bg="#2c2c2c", pady=15)
        header_frame.pack(fill=tk.X)

        tk.Label(header_frame, text="Hiland's Deal Hunter", font=("Helvetica", 22, "bold"), bg="#2c2c2c", fg="#d4af37").pack(side=tk.LEFT, padx=20)
        
        self.scan_btn = tk.Button(header_frame, text="FIND DEALS", command=self.start_scan, 
                                  bg="#d4af37", fg="black", font=("Arial", 12, "bold"), padx=20)
        self.scan_btn.pack(side=tk.RIGHT, padx=20)
        
        self.stop_btn = tk.Button(header_frame, text="STOP", command=self.stop_scan, 
                                  bg="#d9534f", fg="white", font=("Arial", 12, "bold"), padx=10, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT, padx=5)
        
        export_btn = tk.Button(header_frame, text="Export CSV", command=self.export_csv,
                               bg="#444", fg="white", font=("Arial", 10))
        export_btn.pack(side=tk.RIGHT, padx=10)

        # --- Search Bar ---
        search_frame = tk.Frame(self, bg="#2c2c2c", pady=5)
        search_frame.pack(fill=tk.X, padx=20)
        
        tk.Label(search_frame, text="Name:", bg="#2c2c2c", fg="white", font=("Arial", 12)).pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Arial", 11))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind("<KeyRelease>", self.filter_results)

        tk.Label(search_frame, text="Min %:", bg="#2c2c2c", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=(10, 5))
        self.min_disc_var = tk.StringVar(value="0")
        min_entry = tk.Entry(search_frame, textvariable=self.min_disc_var, font=("Arial", 11), width=5)
        min_entry.pack(side=tk.LEFT)
        min_entry.bind("<KeyRelease>", self.filter_results)

        tk.Label(search_frame, text="Max %:", bg="#2c2c2c", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=(10, 5))
        self.max_disc_var = tk.StringVar(value="100")
        max_entry = tk.Entry(search_frame, textvariable=self.max_disc_var, font=("Arial", 11), width=5)
        max_entry.pack(side=tk.LEFT)
        max_entry.bind("<KeyRelease>", self.filter_results)

        tk.Label(search_frame, text="Min $:", bg="#2c2c2c", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=(10, 5))
        self.min_price_var = tk.StringVar(value="0")
        min_price_entry = tk.Entry(search_frame, textvariable=self.min_price_var, font=("Arial", 11), width=6)
        min_price_entry.pack(side=tk.LEFT)
        min_price_entry.bind("<KeyRelease>", self.filter_results)

        tk.Label(search_frame, text="Max $:", bg="#2c2c2c", fg="white", font=("Arial", 12)).pack(side=tk.LEFT, padx=(10, 5))
        self.max_price_var = tk.StringVar(value="500")
        max_price_entry = tk.Entry(search_frame, textvariable=self.max_price_var, font=("Arial", 11), width=6)
        max_price_entry.pack(side=tk.LEFT)
        max_price_entry.bind("<KeyRelease>", self.filter_results)

        # In Stock Checkbox
        self.in_stock_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(search_frame, text="In Stock Only", variable=self.in_stock_var, 
                             bg="#2c2c2c", fg="white", selectcolor="#1f1f1f", activebackground="#2c2c2c", 
                             activeforeground="white", command=self.filter_results)
        chk.pack(side=tk.LEFT, padx=10)

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Ready to hunt for deals.")
        status_lbl = tk.Label(self, textvariable=self.status_var, bg="#1f1f1f", fg="#cccccc", anchor="w", padx=10, pady=5)
        status_lbl.pack(side=tk.BOTTOM, fill=tk.X)

        # --- Results Table ---
        # Configure Treeview Styles for Dark Mode
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#383838", foreground="white", fieldbackground="#383838", rowheight=30, font=("Arial", 10))
        style.configure("Treeview.Heading", background="#505050", foreground="white", font=('Arial', 11, 'bold'))
        style.map('Treeview', background=[('selected', '#d4af37')], foreground=[('selected', 'black')])

        cols = ("discount", "name", "price", "msrp", "savings")
        
        # Frame for Treeview and Scrollbar
        tree_frame = tk.Frame(self, bg="#2c2c2c")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.tree.yview)
        
        self.tree.heading("discount", text="Discount %")
        self.tree.heading("name", text="Product Name")
        self.tree.heading("price", text="Sale Price")
        self.tree.heading("msrp", text="MSRP")
        self.tree.heading("savings", text="Savings ($)")

        self.tree.column("discount", width=120, anchor="center")
        self.tree.column("name", width=500)
        self.tree.column("price", width=100, anchor="e")
        self.tree.column("msrp", width=100, anchor="e")
        self.tree.column("savings", width=100, anchor="e")

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure tag colors
        self.tree.tag_configure("disc_70", foreground="#00ff00")   # Lime
        self.tree.tag_configure("disc_60", foreground="#32cd32")   # LimeGreen
        self.tree.tag_configure("disc_50", foreground="#adff2f")   # GreenYellow
        self.tree.tag_configure("disc_40", foreground="#ffff00")   # Yellow
        self.tree.tag_configure("disc_30", foreground="#ffa500")   # Orange
        self.tree.tag_configure("disc_20", foreground="#ff8c00")   # DarkOrange
        self.tree.tag_configure("disc_10", foreground="#fa8072")   # Salmon
        
        self.tree.bind("<Double-1>", self.on_double_click)

    def start_scan(self):
        self.scan_btn.config(state=tk.DISABLED, text="Scanning...")
        self.stop_btn.config(state=tk.NORMAL)
        self.tree.delete(*self.tree.get_children())
        self.products = []
        self.displayed_products = []
        self.sort_counter = 0
        self.scraper = HilandScraper() # Reset scraper to clear 'seen_links'
        
        # Threading prevents UI freeze
        threading.Thread(target=self.run_scraper, daemon=True).start()

    def stop_scan(self):
        if self.scraper:
            self.scraper.stop()
        self.status_var.set("Stopping scan... Please wait for current tasks to finish.")

    def run_scraper(self):
        self.update_status("Discovering brands...")
        brands = self.scraper.discover_brands()
        
        if self.scraper.stop_event.is_set():
            self.after(0, self.finish_scan)
            return
        
        total_brands = len(brands)
        self.update_status(f"Found {total_brands} brands. Starting parallel scan...")
        
        completed_brands = 0

        # Parallel Execution using ThreadPoolExecutor
        # We use a max_workers of 10-20 to significantly speed up IO bound operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for brand_url in brands:
                if self.scraper.stop_event.is_set(): break
                # Submit each brand as a job
                futures.append(executor.submit(self.scraper.scrape_brand_pages, brand_url, self.add_deal_threadsafe))
            
            for future in concurrent.futures.as_completed(futures):
                completed_brands += 1
                self.update_status(f"Scanning brands... ({completed_brands}/{total_brands})")
                
                if self.scraper.stop_event.is_set():
                    break

        self.after(0, self.finish_scan)

    def update_status(self, msg):
        self.after(0, lambda: self.status_var.set(msg))

    def add_deal_threadsafe(self, deal):
        """Called from worker threads to add a found deal to the list."""
        self.products.append(deal)
        # Update UI in batches or one by one. For simplicity, one by one via main thread.
        self.after(0, lambda: self.insert_row(deal))

    def insert_row(self, deal):
        # Only insert if it matches current search filter
        search_term = self.search_var.get().lower()
        if search_term and search_term not in deal['name'].lower():
            return

        try:
            min_d = float(self.min_disc_var.get())
        except ValueError:
            min_d = 0.0
            
        try:
            max_d = float(self.max_disc_var.get())
        except ValueError:
            max_d = 100.0
            
        try:
            min_p = float(self.min_price_var.get())
        except ValueError:
            min_p = 0.0
            
        try:
            max_p = float(self.max_price_var.get())
        except ValueError:
            max_p = 10000.0
            
        if not (min_d <= deal['discount_pct'] <= max_d) or not (min_p <= deal['sale_price'] <= max_p):
            return

        if self.in_stock_var.get() and not deal.get('in_stock', True):
            return

        self.displayed_products.append(deal)
        self.sort_counter += 1
        
        # Auto-sort based on threshold to keep list fresh but responsive
        if self.sort_counter >= self.SORT_THRESHOLD:
            self.resort_and_refresh()
            self.sort_counter = 0
        else:
            idx = len(self.displayed_products) - 1
            self._insert_single_item(deal, idx)

    def _insert_single_item(self, deal, idx):
        savings = deal['msrp'] - deal['sale_price']
        pct = deal['discount_pct']
        
        tag = "normal"
        if pct >= 70: tag = "disc_70"
        elif pct >= 60: tag = "disc_60"
        elif pct >= 50: tag = "disc_50"
        elif pct >= 40: tag = "disc_40"
        elif pct >= 30: tag = "disc_30"
        elif pct >= 20: tag = "disc_20"
        elif pct >= 10: tag = "disc_10"

        self.tree.insert("", "end", iid=str(idx), values=(
            f"{deal['discount_pct']:.1f}%",
            deal['name'],
            f"${deal['sale_price']:.2f}",
            f"${deal['msrp']:.2f}",
            f"${savings:.2f}"
        ), tags=(tag,))

    def resort_and_refresh(self):
        self.displayed_products.sort(key=lambda x: x['discount_pct'], reverse=True)
        self.tree.delete(*self.tree.get_children())
        for i, deal in enumerate(self.displayed_products):
            self._insert_single_item(deal, i)

    def finish_scan(self):
        self.resort_and_refresh()
        self.status_var.set(f"Scan complete. Found {len(self.products)} deals.")
        self.scan_btn.config(state=tk.NORMAL, text="FIND DEALS")
        self.stop_btn.config(state=tk.DISABLED)

    def filter_results(self, event=None):
        """Re-populates the treeview based on search text and discount filters."""
        query = self.search_var.get().lower()
        
        try:
            min_d = float(self.min_disc_var.get())
        except ValueError:
            min_d = 0.0
            
        try:
            max_d = float(self.max_disc_var.get())
        except ValueError:
            max_d = 100.0
            
        try:
            min_p = float(self.min_price_var.get())
        except ValueError:
            min_p = 0.0
            
        try:
            max_p = float(self.max_price_var.get())
        except ValueError:
            max_p = 10000.0

        self.tree.delete(*self.tree.get_children())
        self.displayed_products = []

        show_stock_only = self.in_stock_var.get()

        filtered = [
            p for p in self.products 
            if query in p['name'].lower() and min_d <= p['discount_pct'] <= max_d and min_p <= p['sale_price'] <= max_p and (not show_stock_only or p.get('in_stock', True))
        ]
        
        # Sort filtered results by discount before showing
        filtered.sort(key=lambda x: x['discount_pct'], reverse=True)

        for deal in filtered:
            self.displayed_products.append(deal)
            idx = len(self.displayed_products) - 1
            self._insert_single_item(deal, idx)

    def export_csv(self):
        if not self.products:
            messagebox.showinfo("Export", "No data to export.")
            return
            
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file_path:
            try:
                with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(["Name", "Sale Price", "MSRP", "Discount %", "In Stock", "Link"])
                    for p in self.products:
                        stock_status = "Yes" if p.get('in_stock', True) else "No"
                        writer.writerow([p['name'], p['sale_price'], p['msrp'], f"{p['discount_pct']:.1f}", stock_status, p['link']])
                messagebox.showinfo("Success", "Data exported successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")

    def on_double_click(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            idx = int(selected_item[0])
            # Ensure we use the displayed products list to match the index
            if idx < len(self.displayed_products):
                url = self.displayed_products[idx]['link']
                webbrowser.open(url)

if __name__ == "__main__":
    app = HilandDealApp()
    app.mainloop()