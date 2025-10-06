import os
import re
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, abort
import sqlite3
import datetime

# Specify the absolute path to the templates folder
template_dir = os.path.abspath('/var/www/appsdir/templates')
linksdb = os.path.abspath('/var/www/appsdir/links.db')
app = Flask(__name__, template_folder=template_dir)
# Category colors configuration - ordered list of colors
CATEGORY_COLORS = [
    "#9e9e9e",  # Gray (for "None" or first category)
    "#2196f3",  # Blue
    "#ff9800",  # Orange
    "#4caf50",  # Green
    "#f44336",  # Red
    "#9c27b0",  # Purple (extra color for future use)
    "#00bcd4",  # Cyan (extra color for future use)
    "#ffeb3b",  # Yellow (extra color for future use)
]
# Default category (first in the database)
DEFAULT_CATEGORY_INDEX = 0
# Add predefined categories
CATEGORIES_LIST = ["None", "Internal", "Development", "Production", "External"]

# Database setup
def init_db(categories):
    """
    Initialize the database with tables and categories.
    Creates the database if it doesn't exist or adds necessary tables/columns if it does.
    """
    db_exists = os.path.exists(linksdb)
    conn = sqlite3.connect(linksdb)
    c = conn.cursor()
    # Create tables if database is new
    if not db_exists:
        # Create links table
        c.execute('''
            CREATE TABLE links
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             url TEXT NOT NULL,
             description TEXT,
             category_id INTEGER,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
             FOREIGN KEY (category_id) REFERENCES categories (id))
        ''')
        # Create categories table
        c.execute('''
            CREATE TABLE categories
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             name TEXT NOT NULL UNIQUE)
        ''')
        for category in categories:
            c.execute("INSERT INTO categories (name) VALUES (?)", (category,))
    else:
        # Check if categories table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
        if not c.fetchone():
            # Create categories table
            c.execute('''
                CREATE TABLE categories
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT NOT NULL UNIQUE)
            ''')
            for category in categories:
                c.execute("INSERT INTO categories (name) VALUES (?)", (category,))
        # Check if category_id column exists in links table
        c.execute("PRAGMA table_info(links)")
        columns = [info[1] for info in c.fetchall()]
        if 'category_id' not in columns:
            c.execute("ALTER TABLE links ADD COLUMN category_id INTEGER REFERENCES categories(id)")
    conn.commit()
    conn.close()

# Initialize the database
init_db(categories=CATEGORIES_LIST)

@app.route('/')
def index():
    # Get sorting and filtering parameters
    sort_by = request.args.get('sort', 'oldest')
    category_filter = request.args.get('category', 'all')
    # Define allowed sort options
    allowed_sort_options = {
        'newest': 'links.created_at DESC',
        'oldest': 'links.created_at ASC',
        'az': 'links.url ASC',
        'za': 'links.url DESC'
    }
    order_clause = allowed_sort_options.get(sort_by, allowed_sort_options['oldest'])
    # Connect to database
    conn = sqlite3.connect(linksdb)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Get all categories for the dropdown
    c.execute('SELECT * FROM categories ORDER BY id')  # Order by ID to match colors
    categories = list(c.fetchall())
    # Build query based on category filter
    if category_filter != 'all' and category_filter.isdigit():
        c.execute(f'''
            SELECT links.*, categories.name as category_name, categories.id as category_id
            FROM links 
            LEFT JOIN categories ON links.category_id = categories.id
            WHERE links.category_id = ?
            ORDER BY {order_clause}
        ''', (category_filter,))
    else:
        c.execute(f'''
            SELECT links.*, categories.name as category_name, categories.id as category_id
            FROM links 
            LEFT JOIN categories ON links.category_id = categories.id
            ORDER BY {order_clause}
        ''')
    links = c.fetchall()
    conn.close()
    # Create a dictionary mapping category IDs to colors
    category_colors = {}
    for i, category in enumerate(categories):
        color_index = min(i, len(CATEGORY_COLORS) - 1)  # Prevent index out of range
        category_colors[category['id']] = CATEGORY_COLORS[color_index]
    return render_template('index.html', 
                          links=links, 
                          categories=categories,
                          category_colors=category_colors,
                          current_sort=sort_by,
                          current_category=category_filter,
                          default_category_index=DEFAULT_CATEGORY_INDEX)


@app.route('/add', methods=['POST'])
def add_link():
    # Get form data
    raw_url = request.form.get('url', '')
    raw_description = request.form.get('description', '')
    category_id = request.form.get('category_id')
    # URL validation
    if not raw_url:
        # Handle empty URL
        return redirect(url_for('index', error="URL cannot be empty"))
    # Basic URL validation
    try:
        # Parse the URL to check if it's valid
        parsed_url = urlparse(raw_url)
        # Check if URL has scheme and netloc (domain)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            return redirect(url_for('index', error="Invalid URL format"))
        # Optional: Whitelist allowed schemes
        if parsed_url.scheme not in ['http', 'https']:
            return redirect(url_for('index', error="Only HTTP and HTTPS URLs are allowed"))
        # Use the parsed and validated URL
        url = raw_url
    except Exception:
        return redirect(url_for('index', error="Invalid URL"))
    # Description sanitization
    # Limit length
    if raw_description and len(raw_description) > 250:  # Set appropriate max length
        raw_description = raw_description[:250]
    # Strip HTML tags (simple approach)
    description = re.sub(r'<[^>]*>', '', raw_description)
    # Convert category_id to integer or None
    if category_id and category_id.isdigit():
        category_id = int(category_id)
    else:
        # Find the ID of the default category (first one)
        conn = sqlite3.connect(linksdb)
        c = conn.cursor()
        c.execute('SELECT id FROM categories ORDER BY id LIMIT 1')
        result = c.fetchone()
        conn.close()
        if result:
            category_id = result[0]
        else:
            category_id = None
    # Create Timestamp
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Save to database with category
    conn = sqlite3.connect(linksdb)
    c = conn.cursor()
    c.execute('INSERT INTO links (url, description, category_id, created_at) VALUES (?, ?, ?, ?)', 
              (url, description, category_id, current_time))
    conn.commit()
    conn.close()
    # Preserve the current sorting and category when redirecting
    sort_by = request.form.get('sort', 'newest')
    category_filter = request.form.get('category', 'all')
    return redirect(url_for('index', sort=sort_by, category=category_filter))

@app.route('/delete/<int:link_id>', methods=['POST'])
def delete_link(link_id):
    # Delete the link from the database
    conn = sqlite3.connect(linksdb)
    c = conn.cursor()
    c.execute('DELETE FROM links WHERE id = ?', (link_id,))
    conn.commit()
    conn.close()
    # Preserve the current sorting and category when redirecting
    sort_by = request.form.get('sort', 'oldest')
    category_filter = request.form.get('category', 'all')
    return redirect(url_for('index', sort=sort_by, category=category_filter))

if __name__ == '__main__':
    # Run on the specified host and port
    app.run(host='0.0.0.0', port=9993, debug=True)
