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

# Database setup
def init_db():
    if not os.path.exists(linksdb):
        conn = sqlite3.connect(linksdb)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE links
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             url TEXT NOT NULL,
             description TEXT,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ''')
        conn.commit()
        conn.close()

# Initialize the database
init_db()

@app.route('/')
def index():
    # Get sorting parameter from query string, default to 'newest'
    sort_by = request.args.get('sort', 'newest')
    # Define a whitelist of allowed sort options and their corresponding SQL clauses
    allowed_sort_options = {
        'newest': 'created_at DESC',
        'oldest': 'created_at ASC',
        'az': 'url ASC',
        'za': 'url DESC'
    }
    # Use the whitelist to get the appropriate ORDER BY clause
    # Default to 'newest' if an invalid option is provided
    order_clause = allowed_sort_options.get(sort_by, allowed_sort_options['newest'])
    # Get all links from the database with the specified ordering
    conn = sqlite3.connect(linksdb)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f'SELECT * FROM links ORDER BY {order_clause}')
    links = c.fetchall()
    conn.close()
    #print(links)
    return render_template('index.html', links=links, current_sort=sort_by)

@app.route('/add', methods=['POST'])
def add_link():
    # Get raw input (url and description)
    # url = request.form['url']
    # description = request.form['description']
    raw_url = request.form.get('url', '')
    raw_description = request.form.get('description', '')
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
    # Strip HTML tags
    # This is a very basic approach
    description = re.sub(r'<[^>]*>', '', raw_description)
    # Timestamp
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Save to database
    conn = sqlite3.connect(linksdb)
    c = conn.cursor()
    c.execute('INSERT INTO links (url, description, created_at) VALUES (?, ?, ?)', 
              (url, description, current_time))
    conn.commit()
    conn.close()
    # Preserve the current sorting when redirecting
    sort_by = request.form.get('sort', 'newest')
    return redirect(url_for('index', sort=sort_by))

@app.route('/delete/<int:link_id>', methods=['POST'])
def delete_link(link_id):
    # Delete the link from the database
    conn = sqlite3.connect(linksdb)
    c = conn.cursor()
    c.execute('DELETE FROM links WHERE id = ?', (link_id,))
    conn.commit()
    conn.close()
    # Preserve the current sorting when redirecting
    sort_by = request.form.get('sort', 'newest')
    return redirect(url_for('index', sort=sort_by))

if __name__ == '__main__':
    # Run on the specified host and port
    app.run(host='0.0.0.0', port=9993, debug=True)
