from flask import Flask, request, redirect, url_for, render_template_string, make_response
import sqlite3
import requests
import datetime

app = Flask(__name__)
DATABASE = 'stocks.db'


def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            adj_close REAL,
            volume INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            ticker TEXT PRIMARY KEY,
            last_query TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()


def get_price_history(ticker):
    """
    Llama al endpoint JSON de Yahoo Finance y retorna:
      - Lista con el histórico (date, open, high, low, close, adj_close, volume).
      - Nombre real de la empresa, si está disponible (shortName). 
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    data = response.json()
    
    if data.get('chart', {}).get('error'):
        return [], None
    
    result = data['chart']['result'][0]
    meta = result.get('meta', {})
    
    short_name = meta.get('shortName')
    fallback_name = meta.get('symbol', ticker)
    company_name = short_name if short_name else fallback_name
    
    timestamps = result.get('timestamp', [])
    indicators = result.get('indicators', {}).get('quote', [{}])[0]
    adjclose = result.get('indicators', {}).get('adjclose', [{}])[0]

    history_data = []
    for i, timestamp in enumerate(timestamps):
        try:
            date = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            record = {
                'date': date,
                'open': indicators.get('open')[i],
                'high': indicators.get('high')[i],
                'low': indicators.get('low')[i],
                'close': indicators.get('close')[i],
                'adj_close': (
                    adjclose.get('adjclose')[i]
                    if adjclose.get('adjclose') and adjclose.get('adjclose')[i]
                    else indicators.get('close')[i]
                ),
                'volume': indicators.get('volume')[i]
            }
            history_data.append(record)
        except Exception:
            continue

    return history_data, company_name

def save_history_to_db(ticker, history):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE ticker = ?", (ticker,))
    for record in history:
        c.execute(
            "INSERT INTO history (ticker, date, open, high, low, close, adj_close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ticker,
                record['date'],
                record['open'],
                record['high'],
                record['low'],
                record['close'],
                record['adj_close'],
                record['volume']
            )
        )
    conn.commit()
    conn.close()

def get_history_from_db(ticker, sort_column='date', order='ASC'):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    allowed_columns = ['date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']
    if sort_column not in allowed_columns:
        sort_column = 'date'
    if order.upper() not in ['ASC', 'DESC']:
        order = 'ASC'
    query = f"SELECT date, open, high, low, close, adj_close, volume FROM history WHERE ticker = ? ORDER BY {sort_column} {order}"
    c.execute(query, (ticker,))
    rows = c.fetchall()
    conn.close()
    return rows

def update_query_log(ticker):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO queries (ticker, last_query) VALUES (?, datetime('now'))", (ticker,))
    conn.commit()
    conn.close()

def get_queries():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT ticker, last_query FROM queries ORDER BY last_query DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def clear_queries():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM queries")
    conn.commit()
    conn.close()

def delete_query(ticker):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM queries WHERE ticker = ?", (ticker,))
    conn.commit()
    conn.close()


index_html = '''

<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="UTF-8">
    <title>FinQuery 📊</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.3/font/bootstrap-icons.css">
    <style>
      body {
        background-color: #F6F8FA;
        color: #333;
      }
      .header-title {
        margin-top: 50px;
        text-align: center;
      }
      .header-title h1 {
        font-size: 2.2rem;
        color: #333;
      }
      .header-title p.lead {
        color: #666;
      }
      
      .search-section {
        margin-top: 30px;
        text-align: center;
      }
      .search-section input.form-control {
        width: 250px;
      }
      
      .carousel-section {
        margin-top: 40px;
      }
      .carousel-control-prev,
      .carousel-control-next {
        display: none;
      }
      
      .company-card {
        margin: 10px;
        padding: 20px;
        border: 1px solid #E2E6EA;
        border-radius: 8px;
        background-color: #FFF;
        transition: box-shadow 0.3s, transform 0.3s;
        text-align: center;
        height: 250px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
      }
      .company-card:hover {
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        transform: translateY(-3px);
      }
      .company-logo {
        width: 60px;
        height: 60px;
        margin: 0 auto 10px auto;
        object-fit: contain;
      }
      .company-card h6 {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 5px;
        color: #333;
      }
      .company-card p {
        margin-bottom: 10px;
        color: #555;
      }
      
      .queries-section {
        margin-top: 40px;
      }
      .queries-section h3 {
        text-align: center;
        margin-bottom: 20px;
        color: #333;
      }
      .list-group-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      
      .site-info {
        margin-top: 40px;
        padding: 20px;
        background-color: #FFF;
        border: 1px solid #E2E6EA;
        border-radius: 8px;
      }
      .site-info h4 {
        margin-bottom: 15px;
        color: #276EF1;
      }
      .site-info p {
        margin-bottom: 10px;
        color: #555;
        font-size: 0.9rem;
        text-align: justify;
      }
      
      footer {
        text-align: center;
        margin-top: 40px;
        margin-bottom: 20px;
        color: #888;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <header class="header-title">
        <h1><u>FinQuery</u>: Explora los datos bursátiles de empresas</h1>
        <p class="lead">Selecciona una empresa del carrusel o ingresa su ticker para ver su histórico de precios.</p>
      </header>
      
      <section class="search-section">
        <form method="post" action="/" class="form-inline justify-content-center">
          <input type="text" name="ticker" class="form-control mr-2" placeholder="Ingresa el ticker (ej. AAPL)">
          <button type="submit" class="btn" style="background-color:#276EF1; color:#FFF;">
            <i class="bi bi-search"></i> Buscar
          </button>
        </form>
      </section>
      <hr>
      <section class="carousel-section">
        <div id="companyCarousel" 
             class="carousel slide" 
             data-ride="carousel" 
             data-pause="hover" 
             data-wrap="true"
             data-interval="3000" >
          <div class="carousel-inner">
            {% for i in range(0, companies|length, 5) %}
            <div class="carousel-item {% if i == 0 %}active{% endif %}">
              <div class="row justify-content-center">
                {% for company in companies[i:i+5] %}
                <div class="col-md-2">
                  <div class="company-card">
                    <img src="{{ url_for('static', filename='images/' ~ company.image) }}" 
                         alt="{{ company.name }}" 
                         class="company-logo">
                    <h6>{{ company.name }}</h6>
                    <p>{{ company.ticker }}</p>
                    <a href="{{ url_for('company', ticker=company.ticker) }}" 
                       class="btn btn-sm" 
                       style="background-color:#276EF1; color:#FFF;">
                      Consultar
                    </a>
                  </div>
                </div>
                {% endfor %}
              </div>
            </div>
            {% endfor %}
          </div>
        </div>
      </section>
      <hr>
      <section class="queries-section">
        <h3 class="text-center">Consultas realizadas</h3>
        <div class="row justify-content-center">
          <div class="col-md-6">
            {% if queries %}
              <ul class="list-group">
                {% for q in queries %}
                  <li class="list-group-item">
                    <span>{{ q[0] }} - Última consulta: {{ q[1] }}</span>
                    <div>
                      <a href="{{ url_for('company', ticker=q[0]) }}" class="btn btn-sm btn-primary mr-2">
                        Ver historial
                      </a>
                      <a href="{{ url_for('delete_query_route', ticker=q[0]) }}" class="btn btn-sm btn-danger" title="Borrar">
                        <i class="bi bi-x-lg"></i>
                      </a>
                    </div>
                  </li>
                {% endfor %}
              </ul>
            {% else %}
              <p class="text-center mt-3">No se han realizado consultas aún.</p>
            {% endif %}
          </div>
        </div>
      </section>
      <section class="site-info">
        <h4>Información del sitio</h4>
        <p><strong>Desarrollo y Tecnología:</strong> Este sitio fue desarrollado utilizando Python y el framework Flask, lo que permite crear aplicaciones web ágiles y escalables. La aplicación ha sido diseñada de manera modular y se basa en tecnologías modernas para ofrecer una experiencia de usuario fluida y profesional.</p>
        <p><strong>Fuente de Datos:</strong> La información bursátil se obtiene a través de técnicas de web scraping y utilizando APIs públicas, en particular la API de Yahoo Finance. Esto garantiza que los datos se actualicen y sean lo más precisos posible, provenientes de fuentes confiables.</p>
        <p><strong>Métodos y Técnicas:</strong> Se emplean métodos de extracción de datos y almacenamiento en bases de datos (SQLite) para guardar y gestionar el histórico de precios. Además, se registran las consultas realizadas para analizar el uso del sistema.</p>
        <p><strong>Licencia y Uso de los Datos:</strong> Todos los datos obtenidos son de libre uso, provienen de fuentes públicas y se utilizan exclusivamente con fines informativos. La aplicación se distribuye bajo una licencia abierta, permitiendo su uso, modificación y redistribución.</p>
        <p><strong>Contribución y Contacto:</strong> El proyecto es de código abierto y cualquier desarrollador o interesado puede contribuir o sugerir mejoras. Para reportar errores, proponer nuevas funcionalidades o colaborar en el desarrollo, ponte en contacto con el autor a través de los canales oficiales.</p>
        <p><strong>Disclaimer:</strong> La información presentada en este sitio tiene fines meramente informativos y no constituye asesoramiento financiero. Se recomienda realizar análisis adicionales antes de tomar cualquier decisión de inversión.</p>
      </section>
      
      <footer>
        <small>Luigi Adducci // Consulta datos bursátiles // &copy; 2025</small>
      </footer>
    </div>
    
    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.5.2/dist/js/bootstrap.bundle.min.js"></script>
  </body>
</html>
'''




@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        ticker = request.form.get('ticker')
        if ticker:
            ticker = ticker.upper().strip()
            return redirect(url_for('company', ticker=ticker))
    queries = get_queries()

    companies = [
        {"name": "Apple Inc.", "ticker": "AAPL", "image": "apple.png"},
        {"name": "Alphabet Inc.", "ticker": "GOOGL", "image": "google.png"},
        {"name": "Microsoft Corp.", "ticker": "MSFT", "image": "microsoft.png"},
        {"name": "Amazon.com Inc.", "ticker": "AMZN", "image": "amazon.png"},
        {"name": "Meta Platforms Inc.", "ticker": "META", "image": "facebook.png"},
        {"name": "Tesla Inc.", "ticker": "TSLA", "image": "tesla.png"},
        {"name": "Netflix Inc.", "ticker": "NFLX", "image": "netflix.png"},
        {"name": "NVIDIA Corp.", "ticker": "NVDA", "image": "nvidia.png"},
        {"name": "Intel Corp.", "ticker": "INTC", "image": "intel.png"},
        {"name": "Adobe Inc.", "ticker": "ADBE", "image": "adobe.png"}
    ]
    return render_template_string(index_html, queries=queries, companies=companies)

@app.route('/company/<ticker>')
def company(ticker):
    sort = request.args.get('sort', 'date')
    order = request.args.get('order', 'ASC')
    history, company_name = get_price_history(ticker)
    if not history:
        return render_template_string(error_html,
                                      error_code=404,
                                      error_message="No Encontrado",
                                      error_description=f"No se encontró información para el ticker: {ticker}")
    save_history_to_db(ticker, history)
    update_query_log(ticker)
    records = get_history_from_db(ticker, sort_column=sort, order=order)
    return render_template_string(company_html, 
                                  ticker=ticker,
                                  company_name=company_name,
                                  records=records,
                                  hide_nav=False)

@app.route('/company/<ticker>/download')
def download_html(ticker):
    records = get_history_from_db(ticker)
    if not records:
        return render_template_string(error_html,
                                      error_code=404,
                                      error_message="No Encontrado",
                                      error_description=f"No se encontró información para el ticker: {ticker}")
    rendered = render_template_string(company_html, 
                                      ticker=ticker, 
                                      company_name=ticker,
                                      records=records, 
                                      hide_nav=True)
    response = make_response(rendered)
    response.headers['Content-Disposition'] = f'attachment; filename={ticker}_historial.html'
    response.headers['Content-Type'] = 'text/html'
    return response

@app.route('/clear_queries')
def clear_queries_route():
    clear_queries()
    return redirect(url_for('index'))

@app.route('/delete_query/<ticker>')
def delete_query_route(ticker):
    delete_query(ticker)
    return redirect(url_for('index'))
  
company_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Histórico de {{ ticker }} - {{ company_name }}</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.3/font/bootstrap-icons.css">
    <style>
        body { background-color: #F6F8FA; }
        .container { margin-top: 30px; }
        .table thead th { 
            background-color: #276EF1; 
            color: white;
            cursor: pointer;
        }
        .table thead th a { color: white; text-decoration: none; }
        .download-btn { margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>{{ ticker }} - {{ company_name }}</h1>
            {% if not hide_nav %}
            <a href="{{ url_for('index') }}" class="btn btn-secondary">
                <i class="bi bi-arrow-left"></i> Volver
            </a>
            {% endif %}
        </div>
        
        <a href="{{ url_for('download_html', ticker=ticker) }}" class="btn btn-success download-btn">
            <i class="bi bi-download"></i> Descargar HTML
        </a>

        <div class="table-responsive">
            <table class="table table-bordered table-hover">
                <thead class="thead-dark">
                    <tr>
                        <th><a href="?sort=date&order={% if sort == 'date' and order == 'ASC' %}DESC{% else %}ASC{% endif %}">Fecha</a></th>
                        <th><a href="?sort=open&order={% if sort == 'open' and order == 'ASC' %}DESC{% else %}ASC{% endif %}">Apertura</a></th>
                        <th><a href="?sort=high&order={% if sort == 'high' and order == 'ASC' %}DESC{% else %}ASC{% endif %}">Máximo</a></th>
                        <th><a href="?sort=low&order={% if sort == 'low' and order == 'ASC' %}DESC{% else %}ASC{% endif %}">Mínimo</a></th>
                        <th><a href="?sort=close&order={% if sort == 'close' and order == 'ASC' %}DESC{% else %}ASC{% endif %}">Cierre</a></th>
                        <th><a href="?sort=adj_close&order={% if sort == 'adj_close' and order == 'ASC' %}DESC{% else %}ASC{% endif %}">Cierre Ajustado</a></th>
                        <th><a href="?sort=volume&order={% if sort == 'volume' and order == 'ASC' %}DESC{% else %}ASC{% endif %}">Volumen</a></th>
                    </tr>
                </thead>
                <tbody>
                    {% for record in records %}
                    <tr>
                        <td>{{ record[0] }}</td>
                        <td>{{ "%.2f"|format(record[1]) }}</td>
                        <td>{{ "%.2f"|format(record[2]) }}</td>
                        <td>{{ "%.2f"|format(record[3]) }}</td>
                        <td>{{ "%.2f"|format(record[4]) }}</td>
                        <td>{{ "%.2f"|format(record[5]) }}</td>
                        <td>{{ "{:,}".format(record[6]) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <footer class="text-center mt-5">
            <small>Luigi Adducci // Consulta datos bursátiles // &copy; 2025</small>
        </footer>
    </div>
</body>
</html>
'''

error_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Error {{ error_code }}</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
</head>
<body>
    <div class="container mt-5">
        <div class="alert alert-danger">
            <h1 class="alert-heading">{{ error_message }}</h1>
            <p>{{ error_description }}</p>
            <hr>
            <a href="{{ url_for('index') }}" class="btn btn-primary">Volver al inicio</a>
        </div>
    </div>
</body>
</html>
'''


@app.errorhandler(404)
def page_not_found(e):
    return render_template_string(error_html,
                                  error_code=404,
                                  error_message="404 - Página No Encontrada",
                                  error_description="La página que buscas no existe."), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template_string(error_html,
                                  error_code=500,
                                  error_message="500 - Error Interno",
                                  error_description="Ocurrió un error en el servidor. Por favor, inténtalo nuevamente más tarde."), 500


if __name__ == '__main__':
    app.run(debug=True)
