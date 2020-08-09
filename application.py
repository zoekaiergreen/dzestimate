from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
import sqlite3
import csv
import re
import matplotlib
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import datetime
import matplotlib.dates as mdates
import matplotlib.ticker as ticker

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

#Use sqlite3 for making database
conn = sqlite3.connect("homes.db", check_same_thread=False)

homes_data = "/Users/Zoe/Desktop/CS50/finalproject/Neighborhood_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_mon.csv"
covid_data = "/Users/Zoe/Desktop/CS50/finalproject/us-counties-NYT.csv"
state_abbrev = "/Users/Zoe/Desktop/CS50/finalproject/state_abbrev.csv"

history_plots = {}

def clear_database():
    c = conn.cursor()
    c.execute("""DROP TABLE IF EXISTS neighborhoods""")
    c.execute("""DROP TABLE IF EXISTS price""")
    c.execute("""DROP TABLE IF EXISTS county_covid""")
    c.execute("""DROP TABLE IF EXISTS state_abbrev""")
    c.execute("""CREATE TABLE neighborhoods (
        id integer primary key autoincrement not null, 
        RegionName text, 
        State text, 
        City text, 
        Metro text,
        County text)""")
    c.execute("""CREATE TABLE price (
        id integer primary key autoincrement not null, 
        date text, 
        price real, 
        region_id integer, 
        foreign key (region_id) references neightborhoods(id))""")
    c.execute("""CREATE TABLE county_covid (
        id integer primary key autoincrement not null,
        county text,
        state text,
        population integer,
        date text,
        cases integer)""")
    c.execute("""CREATE TABLE state_abbrev (
        id integer primary key autoincrement not null,
        state_name text, 
        state_code text)""")
    c.execute("""CREATE INDEX RegionName_index 
        ON neighborhoods (RegionName)""")
    c.execute("""CREATE INDEX State_index 
        ON neighborhoods (State)""")    
    c.execute("""CREATE INDEX City_index 
        ON neighborhoods (City)""")
    c.execute("""CREATE INDEX Metro_index 
        ON neighborhoods (Metro)""")
    c.execute("""CREATE INDEX County_index 
        ON neighborhoods (County)""")
    c.execute("""CREATE INDEX date_index
        ON price (date)""")
    c.execute("""CREATE INDEX price_index 
        ON price (price)""") 
    conn.commit()

def reset_database_homes():
    history_plots = {}
    c = conn.cursor()
    with open(homes_data, "r") as neighborhoods:
        reader = csv.DictReader(neighborhoods)

        for row in reader:
            RegionName = row["RegionName"]
            State = row["State"]
            City = row["City"]
            Metro = row["Metro"]
            County = row["CountyName"]
            Price = {}
            hasanydata = False
            for key in row:
                if re.match("\d{4}-\d{2}-\d{2}", key):
                    if row[key] != "":
                        hasanydata = True
                    Price[key] = row[key]
            if hasanydata:            
                c.execute("""
                    INSERT INTO neighborhoods (RegionName, State, City, Metro, County) 
                    VALUES (:RegionName, :State, :City, :Metro, :County)""",
                {"RegionName":RegionName, "State":State, "City":City, "Metro":Metro, "County":County})
                region_id = c.lastrowid
                for key in Price:
                    c.execute("""
                        INSERT INTO price (date, price, region_id)
                        VALUES (:date, :price, :region_id)""",
                    {"date":key, "price":Price[key], "region_id":region_id})

        conn.commit()


def reset_database_covid():
    c = conn.cursor()
    with open(state_abbrev, "r") as state_abbrevs:
        reader = csv.DictReader(state_abbrevs)

        for row in reader:
            print(row)
            state_name = row["State"]
            state_code = row["Abbreviation"]
            c.execute("""INSERT INTO state_abbrev (state_name, state_code)
                VALUES (:state_name, :state_code)""",
                {"state_name":state_name, "state_code":state_code})
        c.execute("""INSERT INTO state_abbrev (state_name, state_code)
            VALUES ("Puerto Rico", "PR")""")

    c = conn.cursor()
    with open(covid_data, "r") as covid:
        reader = csv.DictReader(covid)

        for row in reader:
            county = row["county"] + " County"
            state = row["state"]
            c.execute("SELECT state_code FROM state_abbrev WHERE state_name = :state_name", {"state_name":state})
            fetch = c.fetchall()
            if len(fetch) == 0:
                continue
    
            state = fetch[0][0]
            date = row["date"]
            cases = row["cases"]
            c.execute("""INSERT INTO county_covid (county, state, date, cases)
                VALUES (:county, :state, :date, :cases)""",
                {"county":county, "state":state, "date":date, "cases":cases})
            
        conn.commit()





@app.route("/", methods=["GET", "POST"])
def index():
    metros = []
    neighborhoods = []
    State = None
    Metro = None
    c = conn.cursor()
    c.execute("""SELECT DISTINCT State FROM neighborhoods ORDER BY State ASC""")
    states = c.fetchall()
    conn.commit()
    if request.method == "POST" and request.form.get("state"):
        c = conn.cursor()
        State = request.form.get("state")
        c.execute("""SELECT DISTINCT Metro FROM neighborhoods WHERE State = :State ORDER BY Metro ASC""",
            {"State":State})
        metros = c.fetchall()
        conn.commit()
        if request.form.get("metro"):
            c = conn.cursor()
            Metro = request.form.get("metro")
            c.execute("""SELECT DISTINCT RegionName FROM neighborhoods WHERE State = :State AND Metro = :Metro ORDER BY RegionName ASC""",
                {"State":State, "Metro":Metro})
            neighborhoods = c.fetchall()
            conn.commit()
    return render_template("/index.html", states=states, State=State, metros=metros, Metro=Metro, neighborhoods=neighborhoods)

@app.route("/plot", methods=["GET", "POST"])
def plot():
    if request.method == "GET":
        neighborhood = request.args.get("neighborhood")
        metro = request.args.get("Metro")
        dates = []
        y = []
        # x axis values 
        c = conn.cursor()
        c.execute("""SELECT date, price
                    FROM price
                    WHERE region_id IN
                        (SELECT id
                        FROM neighborhoods
                        WHERE RegionName = :neighborhood AND Metro = :metro)""",
                    {"neighborhood":neighborhood, "metro":metro })
        prices = c.fetchall()
        conn.commit()
        c = conn.cursor()
        c.execute("""SELECT DISTINCT State FROM neighborhoods
            WHERE RegionName = :neighborhood AND Metro = :metro""",
            {"neighborhood":neighborhood, "metro":metro })
        state = c.fetchall()[0][0]
        conn.commit()
        for data in prices:
            try:
                y.append(float(data[1]))   
                dates.append(data[0])
            except ValueError:
                pass
        
        location = neighborhood + ", " + state
        
        x = [datetime.datetime.strptime(d,"%Y-%m-%d").date() for d in dates]

        matplotlib.use('agg')
        plt.figure()

        ax = plt.gca()
        formatter = mdates.DateFormatter("%Y-%m-%d")
        ax.xaxis.set_major_formatter(formatter)

        ay = plt.gca()
        formattery = ticker.FormatStrFormatter('$%1.2f')
        ay.yaxis.set_major_formatter(formattery)
        
        plt.xticks(rotation=45)
        # https://stackoverflow.com/questions/6682784/reducing-number-of-plot-ticks
        ax.xaxis.set_major_locator(plt.MaxNLocator(10))
        ax.yaxis.set_major_locator(plt.MaxNLocator(10))

        # plotting the points  
        plt.plot(x, y) 

        # naming the x axis 
        plt.xlabel('Dates') 
        # naming the y axis 
        plt.ylabel('Average Cost of Home') 
        
        # giving a title to my graph 
        plt.title(location) 

        #layout plot
        plt.tight_layout()
        
        #https://stackoverflow.com/questions/31492525/converting-matplotlib-png-to-base64-for-viewing-in-html-template
        figfile = BytesIO()
        plt.savefig(figfile, format='png')
        figfile.seek(0)  # rewind to beginning of file
        figdata_png = base64.b64encode(figfile.getvalue())
        result = figdata_png.decode("utf8")
        history_plots[location] = result
        return render_template("/plot.html", result=result)

@app.route("/history", methods=["GET", "POST"])
def history():
    if request.method == "GET":
        Neighborhood = None
        current_plot = None
        return render_template("/history.html", history_plots=history_plots, Neighborhood=Neighborhood, current_plot=current_plot)
    else:
        Neighborhood = request.form.get("history_location")
        print(Neighborhood)
        current_plot = history_plots[Neighborhood]
        return render_template("/history.html", history_plots=history_plots, Neighborhood=Neighborhood, current_plot=current_plot)


@app.route("/compare", methods=["GET", "POST"])
def compare():
    if request.method == "GET":
        current_plot = None
        return render_template("/compare.html", history_plots=history_plots, current_plot=current_plot)
    else:
        locations = request.form.getlist("neighborhood")
        print(locations)
        y_values = {}
        x_values = {}
        for item in locations:
            location = item.split(', ')
            neighborhood = location[0]
            state = location[1]
            dates = []
            y = []
            c = conn.cursor()
            c.execute("""SELECT date, price
                        FROM price
                        WHERE region_id IN
                        (SELECT id
                        FROM neighborhoods
                        WHERE RegionName = :neighborhood AND State = :state)""",
                        {"neighborhood":neighborhood, "state":state })
            prices = c.fetchall()
            conn.commit()

            #get ys
            for data in prices:
                try:
                    y.append(float(data[1]))   
                    dates.append(data[0])
                except ValueError:
                    pass
            
            #append ys to data for use in plots
            y_values[item] = y

            #get xs
            x = [datetime.datetime.strptime(d,"%Y-%m-%d").date() for d in dates]

            #appendxs to data for use in plots
            x_values[item] = x
        
        matplotlib.use('agg')
        plt.figure()

        ax = plt.gca()
        formatter = mdates.DateFormatter("%Y-%m-%d")
        ax.xaxis.set_major_formatter(formatter)

        ay = plt.gca()
        formattery = ticker.FormatStrFormatter('$%1.2f')
        ay.yaxis.set_major_formatter(formattery)
        
        plt.xticks(rotation=45)
        # https://stackoverflow.com/questions/6682784/reducing-number-of-plot-ticks
        ax.xaxis.set_major_locator(plt.MaxNLocator(10))
        ax.yaxis.set_major_locator(plt.MaxNLocator(10))

        # plotting the points
        for item in locations:
            x = x_values[item]
            y = y_values[item]
            print(item)
            plt.plot(x, y, label=item) 

        # naming the x axis 
        plt.xlabel('Dates') 
        # naming the y axis 
        plt.ylabel('Average Cost of Home') 
        
        # giving a title to my graph 
        plt.title("Comparison chart") 

        #legend
        plt.legend(bbox_to_anchor=(0, 0, 1, 1), bbox_transform=plt.gcf().transFigure, shadow=True)

        #layout plot
        plt.tight_layout()
        
        #https://stackoverflow.com/questions/31492525/converting-matplotlib-png-to-base64-for-viewing-in-html-template
        figfile = BytesIO()
        plt.savefig(figfile, format='png')
        figfile.seek(0)  # rewind to beginning of file
        figdata_png = base64.b64encode(figfile.getvalue())
        result = figdata_png.decode("utf8")
        current_plot = result
        return render_template("/compare.html", history_plots=history_plots, current_plot=current_plot)

@app.route("/coronavirus", methods=["GET", "POST"])
def coronavirus():
    if request.method == "GET":
        current_plot = None
        covid_bool = True
        return render_template("/coronavirus.html", history_plots=history_plots, current_plot=current_plot, covid_bool=covid_bool)
    else:
        covid_bool = False
        locations = request.form.getlist("neighborhood")
        counties = []
        zillow_data = {} # (county, state) -> [(neighborhood, xs, ys)]
        for item in locations:
            location = item.split(', ')
            neighborhood = location[0]
            state = location[1]
            dates = []
            y = []
            c = conn.cursor()
            c.execute("""SELECT date, price
                        FROM price
                        WHERE region_id IN
                        (SELECT id
                        FROM neighborhoods
                        WHERE RegionName = :neighborhood AND State = :state)""",
                        {"neighborhood":neighborhood, "state":state })
            prices = c.fetchall()
            conn.commit()
            c = conn.cursor()
            c.execute("""SELECT DISTINCT County FROM neighborhoods
                WHERE RegionName = :neighborhood AND State = :state""",
                {"neighborhood":neighborhood, "state":state })
            county_results = c.fetchall()
            print("county_results: ", county_results)
            county = county_results[0][0]

            key = (county, state)

            conn.commit()
            counties.append(key)
            #get ys
            for data in prices:
                try:
                    y.append(float(data[1]))   
                    dates.append(data[0])
                except ValueError:
                    pass

            #get xs
            x = [datetime.datetime.strptime(d,"%Y-%m-%d").date() for d in dates]

            if key not in zillow_data:
                zillow_data[key] = []
            zillow_data[key].append((neighborhood, x, y))
        
        matplotlib.use('agg')
        plt.figure()

        _, ax = plt.subplots()

        # instantiate a second axes that shares the same x-axis
        ax2 = ax.twinx() 

        formatter = mdates.DateFormatter("%Y-%m-%d")
        ax.xaxis.set_major_formatter(formatter)

        #ay = plt.gca()
        formattery = ticker.FormatStrFormatter('$%1.2f')
        ax.yaxis.set_major_formatter(formattery)
        


        # https://stackoverflow.com/questions/6682784/reducing-number-of-plot-ticks
        ax.xaxis.set_major_locator(plt.MaxNLocator(10))
        ax.yaxis.set_major_locator(plt.MaxNLocator(10))



        ax2.set_ylabel('Cases')
        ax2.yaxis.set_major_locator(plt.MaxNLocator(10))

        for item in counties:
            y = []
            dates = []
            c = conn.cursor()
            c.execute("""SELECT date, cases FROM county_covid
            WHERE county = :county AND state = :state""",
            {"county":item[0], "state":item[1]})
            cases = c.fetchall()
            if cases:    
                conn.commit()

                if item not in zillow_data:
                    continue

                for neighborhood, zillow_x, zillow_y in zillow_data[item]:
                    # Plot Zillow data.
                    label = "{}, {}".format(neighborhood, item[1])
                    ax.plot(zillow_x, zillow_y, label=label, linewidth=0.5)

                for data in cases:
                    try:
                        y.append(float(data[1]))   
                        dates.append(data[0])
                    except ValueError:
                        pass
                
                x = [datetime.datetime.strptime(d,"%Y-%m-%d").date() for d in dates]

                label = item[0] + ", " + item[1] + "(COVID)"
                ax2.plot(x, y, label=label, linewidth=2, linestyle='--')
                covid_bool = True

        # naming the x axis 
        ax.set_xlabel('Dates')
        ax.set_xlim([datetime.date(2019, 10, 31), datetime.datetime.today()])

        # naming the y axis 
        ax.set_ylabel('Average Cost of Home') 
        
        # giving a title to my graph 
        plt.title("Comparison chart") 

        #legend
        handles1, labels1 = ax.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        handles = handles1 + handles2
        labels = labels1 + labels2
        plt.legend(handles, labels, loc="lower left", bbox_to_anchor=(-.1, -.404, 1.1, .102), ncol=2, mode="expand", borderaxespad=0., shadow=True)

        plt.draw()

        ax.set_xticklabels(ax.get_xticklabels(), rotation=45)

        #layout plot
        plt.tight_layout()
        
        #https://stackoverflow.com/questions/31492525/converting-matplotlib-png-to-base64-for-viewing-in-html-template
        figfile = BytesIO()
        plt.savefig(figfile, format='png')
        figfile.seek(0)  # rewind to beginning of file
        figdata_png = base64.b64encode(figfile.getvalue())
        result = figdata_png.decode("utf8")
        current_plot = result
        return render_template("/coronavirus.html", history_plots=history_plots, current_plot=current_plot, covid_bool=covid_bool)
    

@app.route("/admin", methods=["GET"])
def admin():
    if request.method == "GET":
        return render_template("/admin.html", reset=False, clear=False)

@app.route("/resetdb", methods=["POST"])
def resetdb():
    clear_database()
    reset_database_homes()
    reset_database_covid()
    return jsonify(success=True)
          



# We can also close the connection if we are done with it.
# Just be sure any changes have been committed or they will be lost.
#conn.close()