# Hiland's Cigars - Discount Hunter Application

This application is a specialized web scraper and deal finder for Hiland's Cigars. It provides a user-friendly GUI to scan the website for cigar deals and analyze discounts.

## Features:

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

## Building the Executable

To create a standalone Windows executable (`.exe`):

1.  Ensure you have Python installed.
2.  Run the provided batch script:
    ```batch
    build_exe.bat
    ```
3.  The output will be located in the `dist/` directory.
