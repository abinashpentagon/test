from flask import Flask, render_template, request, redirect,session, url_for, flash, abort, make_response
import mysql.connector
from mysql.connector import Error
from werkzeug.utils import secure_filename
import json
import os
import re
from flask import jsonify
import time


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

app.config['UPLOAD_FOLDER'] = r'C:\Users\saran\OneDrive\Desktop\MCC - Reseacher Profile\static\uploads'


def get_db_connection():
    """Establish a new database connection."""
    return mysql.connector.connect(
        user='root',
        password='1708',
        host='localhost',
        database='staff_details'
    )

DEFAULT_PASSWORD = 'Mcc@123'
EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@mcc\.edu\.in$'

def validate_email(email):
    return re.match(EMAIL_PATTERN, email) is not None

@app.route('/index')
def index():
    # Total staff in the college
    total_college_staff = 300
    
    # Get the total number of staff from the database
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("SELECT COUNT(*) FROM details")
    total_staff_in_db = cur.fetchone()[0]
    cur.close()

    remaining_staff = total_college_staff - total_staff_in_db

    # Fetch department-wise staff counts
    cur = connection.cursor()
    cur.execute("SELECT department, COUNT(*) FROM details GROUP BY department")
    department_counts = cur.fetchall()
    cur.close()

    # Fetch color settings
    cur = connection.cursor(dictionary=True)
    cur.execute("SELECT header_color, sidebar_color FROM color_settings WHERE id = 1")
    color_settings = cur.fetchone()
    cur.close()
    connection.close()

    return render_template(
        'index.html', 
        total_college_staff=total_college_staff, 
        total_staff_in_db=total_staff_in_db, 
        remaining_staff=remaining_staff,
        department_counts=department_counts,
        header_color=color_settings['header_color'],
        sidebar_color=color_settings['sidebar_color']
    )

@app.route('/save_colors', methods=['POST'])
def save_colors():
    header_color = request.form.get('header_color')
    sidebar_color = request.form.get('sidebar_color')
    
    connection = get_db_connection()
    cur = connection.cursor()
    
    # Assuming you have a single row in the `color_settings` table with `id=1`
    cur.execute("""
        UPDATE color_settings 
        SET header_color = %s, sidebar_color = %s 
        WHERE id = 1
    """, (header_color, sidebar_color))
    
    connection.commit()
    cur.close()
    connection.close()
    
    flash('Colour changed succesfull', 'success')
    return redirect(url_for('index'))
   

@app.route('/tables')
def tables():
    # Fetch all staff details from the database
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("SELECT * FROM details")
    staff_details = cur.fetchall()
    cur.close()
    connection.close()
    
    return render_template('tables.html', staff_details=staff_details)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            return redirect(url_for('login'))
        
         # Check for the specific admin email and password
        if email == 'admin@mcc.edu.in' and password == 'Mcc@12345':
            session['user_type'] = 'admin'
            
            return redirect(url_for('index'))


        if not validate_email(email):
            flash('Invalid email format. Please use an @mcc.edu.in address.', 'error')
            return redirect(url_for('login'))

        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Fetch user details from the staff table
            cursor.execute("SELECT password, password_changed, profile_completed FROM staff WHERE email=%s", (email,))
            user = cursor.fetchone()

            if user:
                stored_password, password_changed, profile_completed = user

                if stored_password == DEFAULT_PASSWORD:
                    if password == DEFAULT_PASSWORD:
                        # Redirect to reset_password with the email parameter
                        return redirect(url_for('reset_password', email=email))
                    else:
                        flash('Invalid credentials', 'error')
                        return redirect(url_for('login'))
                elif stored_password == password:
                    if password_changed == 0:
                        flash('Password has not been set up yet', 'error')
                        return redirect(url_for('login'))
                    elif profile_completed == 0:
                        # Redirect to the form page if profile is not completed
                        return redirect(url_for('submit_form'))
                    else:
                        session['user_type'] = 'user'
                        # Redirect to the profile page if profile is completed
                        return redirect(url_for('profile', email=email))
                else:
                    flash('Invalid credentials', 'error')
                    return redirect(url_for('login'))
            else:
                flash('User does not exist', 'error')
                return redirect(url_for('login'))

        except Error as e:
            print(f"Database error: {e}")
            flash('An error occurred while processing your request.', 'error')
            return redirect(url_for('login'))

    # Render the login page with flash messages if there are any
    return render_template('login.html')


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email')

    if not email:
        flash('Invalid request. Email is required.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash('Password cannot be empty.', 'error')
        elif new_password != confirm_password:
            flash('Passwords do not match.', 'error')
        elif len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
        else:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE staff SET password=%s, password_changed=TRUE WHERE email=%s",
                (new_password, email)  # Store plain text password
            )
            connection.commit()
            flash('Password has been successfully reset.', 'success')
            return redirect(url_for('login'))

    # Render the template with an empty message if no errors
    return render_template('reset_password.html', email=email, message='')

@app.route('/submit_form', methods=['GET', 'POST'])
def submit_form():
    if request.method == 'POST':
        # Retrieve personal information
        name = request.form.get('name')
        title = request.form.get('title')
        institution = request.form.get('institution')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        website = request.form.get('website')
        profile_picture = request.files.get('profile_picture')
        department = request.form.get('department')
        research_areas = [line.strip() for line in request.form.get('research_areas', '').split('\n') if line.strip()]

        default_picture_filename = 'default.webp'
        profile_picture = request.files.get('profile_picture')
        profile_picture_filename = default_picture_filename

        if profile_picture:
        # Extract the file extension
            file_extension = os.path.splitext(profile_picture.filename)[1]
        # Create a new filename using the user's name
            profile_picture_filename = f"{secure_filename(name)}{file_extension}"
            profile_picture_path = os.path.join(app.config['UPLOAD_FOLDER'], profile_picture_filename)
            profile_picture.save(profile_picture_path)
        
        print(f"Profile picture filename: {profile_picture_filename}")
        print(f"Profile picture path: {profile_picture_path}")

        # Retrieve dynamic research IDs
        research_ids_titles = [request.form.get(f'research_ids_title_{i+1}').strip() for i in range(50) if request.form.get(f'research_ids_title_{i+1}')]
        research_ids_links = [request.form.get(f'research_ids_id_{i+1}').strip() for i in range(50) if request.form.get(f'research_ids_id_{i+1}')]
        
        # Retrieve dynamic education fields
        education_degrees = [request.form.get(f'education_degree_{i+1}').strip() for i in range(50) if request.form.get(f'education_degree_{i+1}')]
        education_colleges = [request.form.get(f'education_college_{i+1}').strip() for i in range(50) if request.form.get(f'education_college_{i+1}')]
        education_durations = [request.form.get(f'education_duration_{i+1}').strip() for i in range(50) if request.form.get(f'education_duration_{i+1}')]
        
        # Retrieve dynamic funding fields
        funding_items = [request.form.get(f'funding_{i+1}').strip() for i in range(10) if request.form.get(f'funding_{i+1}')]
        
        # Retrieve dynamic publications fields
        publications_titles = [request.form.get(f'publications_title_{i+1}').strip() for i in range(50) if request.form.get(f'publications_title_{i+1}')]
        publications_links = [request.form.get(f'publications_link_{i+1}').strip() for i in range(50) if request.form.get(f'publications_link_{i+1}')]
        
        # Retrieve other sections
        career_highlights = [line.strip() for line in request.form.get('career_highlights', '').split('\n') if line.strip()]
        research_career = [line.strip() for line in request.form.get('research_career', '').split('\n') if line.strip()]
        
        # Convert lists to JSON strings
        research_ids_json = json.dumps([{"title": title, "id": link} for title, link in zip(research_ids_titles, research_ids_links)])
        education_json = json.dumps([{"degree": degree, "college": college, "duration": duration} for degree, college, duration in zip(education_degrees, education_colleges, education_durations)])
        funding_json = json.dumps(funding_items)
        publications_json = json.dumps([{"title": title, "link": link} for title, link in zip(publications_titles, publications_links)])

        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            insert_query = """
            INSERT INTO details (name, title, institution, email, phone, address, website, profile_picture, department, research_areas, research_ids, education, funding, publications, career_highlights, research_career)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                name, title, institution, email, phone, address, website, profile_picture_filename, department,
                '\n'.join(research_areas), research_ids_json, education_json, funding_json, publications_json,
                '\n'.join(career_highlights), '\n'.join(research_career)
            ))
            connection.commit()
            
            # Update profile_completed column in staff table
            update_query = """
            UPDATE staff SET profile_completed = 1 WHERE email = %s
            """
            cursor.execute(update_query, (email,))
            connection.commit()
            
            cursor.close()
            connection.close()
            
            flash('Form submitted successfully!', 'success')
        except Exception as e:
            print(f"Error: {e}")
            # Flash an error message
            flash('An error occurred while submitting the form. Please try again.', 'error')
        
        return redirect(url_for('profile'))

    return render_template('form.html')

@app.route('/profile')
def profile():
    email = request.args.get('email')  # Get the email parameter

    if not email:
        return redirect(url_for('login', message='Email is required to view the profile.'))

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Query to get user details
        query = """
        SELECT
            id, name, title, institution, email, phone, address, website,
            profile_picture, department, research_areas, research_ids, education,
            funding, publications, career_highlights, research_career
        FROM details
        WHERE email = %s
        """
        cursor.execute(query, (email,))
        user_data = cursor.fetchone()

        if not user_data:
            abort(404, description="User not found")


        # Convert JSON strings back to lists
        user_data['research_areas'] = user_data['research_areas'].split('\n') if user_data['research_areas'] else []
        user_data['research_ids'] = json.loads(user_data['research_ids']) if user_data['research_ids'] else []
        user_data['education'] = json.loads(user_data['education']) if user_data['education'] else []
        user_data['funding'] = json.loads(user_data['funding']) if user_data['funding'] else []
        user_data['publications'] = json.loads(user_data['publications']) if user_data['publications'] else []
        user_data['career_highlights'] = user_data['career_highlights'].split('\n') if user_data['career_highlights'] else []
        user_data['research_career'] = user_data['research_career'].split('\n') if user_data['research_career'] else []

        cursor.close()
        connection.close()
        

        return render_template('profile.html', user=user_data)

    except Error as e:
        print(f"Error: {e}")
        abort(500, description="An error occurred while retrieving user data.")




@app.route('/', methods=['GET', 'POST'])
@app.route('/dashboard', methods=['GET'])
def dashboard():
    search_query = request.args.get('search', '').strip()
    selected_department = request.args.get('department', '').strip()

    staff_details = []
    departments_with_staff = {}

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch all departments and their staff details
        query_departments = "SELECT DISTINCT department FROM details"
        cursor.execute(query_departments)
        departments = cursor.fetchall()

        for department in departments:
            dept_name = department['department']
            query_staff = "SELECT id, name FROM details WHERE department = %s"
            cursor.execute(query_staff, (dept_name,))
            staff_in_dept = cursor.fetchall()
            departments_with_staff[dept_name] = staff_in_dept

        if selected_department:
            query = """
            SELECT id, profile_picture, name, title, institution, department, email, phone, address, website, 
                   research_areas, research_ids, education, funding, publications, career_highlights, research_career
            FROM details
            WHERE department = %s
            ORDER BY id DESC
            """
            cursor.execute(query, (selected_department,))
        else:
            search_term = f"%{search_query}%"
            query = """
            SELECT id, profile_picture, name, title, institution, department, email, phone, address, website, 
                   research_areas, research_ids, education, funding, publications, career_highlights, research_career
            FROM details
            WHERE name LIKE %s OR title LIKE %s OR department LIKE %s OR institution LIKE %s OR email LIKE %s
            OR phone LIKE %s OR address LIKE %s OR website LIKE %s OR research_areas LIKE %s OR research_ids LIKE %s
            OR education LIKE %s OR funding LIKE %s OR publications LIKE %s OR career_highlights LIKE %s
            OR research_career LIKE %s
            ORDER BY id DESC
            """
            parameters = [search_term] * 15
            cursor.execute(query, parameters)

        staff_details = cursor.fetchall()
        
        for detail in staff_details:
                detail['matched_text'] = extract_matched_text(detail, search_query)
        cursor.close()
        connection.close()

    except Error as e:
        print(f"Database error: {e}")
        flash('An error occurred while processing your request.', 'danger')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # If the request is AJAX, return JSON
        return jsonify(staff_details)
    else:
        # Otherwise, render the dashboard template
        return render_template('dashboard.html', 
                               staff_details=staff_details,
                               departments_with_staff=departments_with_staff,
                               search_query=search_query)
    
def clean_json_text(text):
    """Remove JSON-like symbols and special characters from the text."""
    # Remove JSON brackets, quotes, and extra whitespace
    cleaned_text = re.sub(r'[\[\]\"\'\s]+', ' ', text).strip()
    # Remove any URLs from the text
    cleaned_text = re.sub(r'http[s]?://\S+', '', cleaned_text).strip()
    return cleaned_text

def extract_matched_text(detail, search_query):
    """
    Extract the first matching word from the given detail dictionary based on search_query.
    If a match is found, return the matching text; otherwise, return 'No match found'.
    """
    search_query = search_query.lower()

    # Function to find and return the closest match in a list of words
    def find_closest_match(text, query):
        words = re.findall(r'\b\w+\b', text)  # Tokenize the text into words
        for word in words:
            if query in word.lower():
                return word  # Return the word containing the search query
        return None

    # Check if the search query matches the name field
    if 'name' in detail and search_query in detail['name'].lower():
        return find_closest_match(detail['name'], search_query)

    # Check other fields for a match
    for key, value in detail.items():
        if isinstance(value, str):
            # Check if the value is JSON-encoded
            try:
                json_value = json.loads(value)
                if isinstance(json_value, list):
                    # Handle JSON list
                    for item in json_value:
                        if isinstance(item, dict):
                            item_text = ' '.join(item.values())
                            closest_match = find_closest_match(item_text, search_query)
                            if closest_match:
                                return closest_match
                        elif isinstance(item, str):
                            closest_match = find_closest_match(item, search_query)
                            if closest_match:
                                return closest_match
                elif isinstance(json_value, dict):
                    # Handle JSON dict
                    item_text = ' '.join(json_value.values())
                    closest_match = find_closest_match(item_text, search_query)
                    if closest_match:
                        return closest_match
                else:
                    # Handle plain text in JSON
                    closest_match = find_closest_match(value, search_query)
                    if closest_match:
                        return closest_match
            except (json.JSONDecodeError, TypeError):
                # Not a JSON-encoded string, handle as plain text
                if key in ['research_areas', 'career_highlights', 'research_career']:
                    # Special handling for specific fields
                    items = value.split('\n')
                    for item in items:
                        closest_match = find_closest_match(item, search_query)
                        if closest_match:
                            return closest_match
                else:
                    closest_match = find_closest_match(value, search_query)
                    if closest_match:
                        return closest_match

    return 'Match found'


@app.route('/view_details/<int:id>')
def view_details(id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch color settings (Assuming there is a table named color_settings with an id of 1)
        cursor.execute("SELECT header_color, sidebar_color FROM color_settings WHERE id = 1")
        color_settings = cursor.fetchone()
       

        query = "SELECT * FROM details WHERE id = %s"
        cursor.execute(query, (id,))
        details = cursor.fetchone()

        if details:
            try:
                details['research_ids'] = json.loads(details['research_ids']) if details['research_ids'] else []
            except json.JSONDecodeError as e:
                print("Error decoding research_ids:", e)
                details['research_ids'] = []

            try:
                details['education'] = json.loads(details['education']) if details['education'] else []
            except json.JSONDecodeError as e:
                print("Error decoding education:", e)
                details['education'] = []

            try:
                details['funding'] = json.loads(details['funding']) if details['funding'] else []
            except json.JSONDecodeError as e:
                print("Error decoding funding:", e)
                details['funding'] = []

            try:
                details['publications'] = json.loads(details['publications']) if details['publications'] else []
            except json.JSONDecodeError as e:
                print("Error decoding publications:", e)
                details['publications'] = []

            if details.get('career_highlights'):
                details['career_highlights'] = [item.strip() for item in details['career_highlights'].split('\n') if item.strip()]
            
            if details.get('research_career'):
                details['research_career'] = [item.strip() for item in details['research_career'].split('\n') if item.strip()]

            if details.get('research_areas'):
                details['research_areas'] = [item.strip() for item in details['research_areas'].split('\n') if item.strip()]

        cursor.close()
        connection.close()

        if details:
            return render_template('view_details.html', details=details, colors=color_settings)
        else:
            flash('No details found for this ID.', 'warning')
            return redirect(url_for('dashboard'))
    except Error as e:
        print(f"Database error: {e}")
        flash('An error occurred while fetching data from the database.', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/update_profile/<email>', methods=['GET'])
def render_update_page(email):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM details WHERE email = %s"
        
        cursor.execute(query, (email,))
        staff = cursor.fetchone()
        cursor.close()
        connection.close()
        print("Fetched staff details:", staff)

        if staff:
            # Handle JSON fields
            try:
                staff['research_ids'] = json.loads(staff['research_ids']) if staff['research_ids'] else []
                staff['education'] = json.loads(staff['education']) if staff['education'] else []
                staff['funding'] = json.loads(staff['funding']) if staff['funding'] else []
                staff['publications'] = json.loads(staff['publications']) if staff['publications'] else []
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")

            staff['career_highlights'] = [item.strip() for item in staff['career_highlights'].split('\n') if item.strip()]
            staff['research_career'] = [item.strip() for item in staff['research_career'].split('\n') if item.strip()]
            staff['research_areas'] = [area.strip() for area in staff['research_areas'].split(',') if area.strip()]


        return render_template('update.html', staff=staff)

    except Error as e:
        print(f"Database error: {e}")
        flash('An error occurred while fetching data from the database.', 'danger')
        return redirect(url_for('profile'))

@app.route('/update_profile/<email>', methods=['POST'])
def update_profile(email):
    if request.method == 'POST':
        try:
            for key in request.form:
                print(f"{key}: {request.form[key]}")

            # Debug form data
            print("Form data:", request.form)
            print("File data:", request.files)

            # Retrieve personal information
            name = request.form.get('name')
            title = request.form.get('title')
            institution = request.form.get('institution')
            phone = request.form.get('phone')
            address = request.form.get('address')
            website = request.form.get('website')
            department = request.form.get('department')
            research_areas = [line.strip() for line in request.form.get('research_areas', '').split('\n') if line.strip()]

            # Handle profile picture file upload
            connection = get_db_connection()
            cursor = connection.cursor()

    # Retrieve the current profile picture filename from the database
            cursor.execute("SELECT profile_picture FROM details WHERE email=%s", (email,))
            result = cursor.fetchone()
            old_profile_picture_filename = result[0] if result else None
            cursor.close()

    # Handle profile picture file upload
            profile_picture = request.files.get('profile_picture')
            if profile_picture and profile_picture.filename:
        # Extract the file extension from the original file
                file_extension = os.path.splitext(profile_picture.filename)[1]
        
        # Generate a new filename using the user's name and a timestamp
                timestamp = int(time.time())  # Current timestamp as an integer
                profile_picture_filename = f"{secure_filename(name)}_{timestamp}{file_extension}"
        
        # Create the full path to save the file
                profile_picture_path = os.path.join(app.config['UPLOAD_FOLDER'], profile_picture_filename)
        
        # Save the new profile picture
                profile_picture.save(profile_picture_path)
            else:
        # Keep the old profile picture if no new file is uploaded
                profile_picture_filename = old_profile_picture_filename
    
    # Now you would update the database with the new filename
            cursor = connection.cursor()
            cursor.execute("UPDATE details SET profile_picture=%s WHERE email=%s", (profile_picture_filename, email))
            connection.commit()
            cursor.close()

    # Close the database connection
            connection.close()
            # Retrieve dynamic fields
            
            research_ids_titles = [request.form.get(f'research_ids_title_{i}', '').strip() for i in range(50)]
            research_ids_links = [request.form.get(f'research_ids_id_{i}', '').strip() for i in range(50)]
            education_degrees = [request.form.get(f'education_degree_{i}', '').strip() for i in range(50)]
            education_colleges = [request.form.get(f'education_college_{i}', '').strip() for i in range(50)]
            education_durations = [request.form.get(f'education_duration_{i}', '').strip() for i in range(50)]
            funding_items = [request.form.get(f'funding_{i}', '').strip() for i in range(50)]
            publications_titles = [request.form.get(f'publications_title_{i}', '').strip() for i in range(50)]
            publications_links = [request.form.get(f'publications_link_{i}', '').strip() for i in range(50)]
            career_highlights = [line.strip() for line in request.form.get('career_highlights', '').split('\n') if line.strip()]
            research_career = [line.strip() for line in request.form.get('research_career', '').split('\n') if line.strip()]

            # Remove empty items from dynamic lists
            funding_items = list(filter(None, funding_items))
            publications = [{"title": title, "link": link} for title, link in zip(publications_titles, publications_links) if title and link]
            research_ids = [{"title": title, "id": link} for title, link in zip(research_ids_titles, research_ids_links) if title and link]
            education = [{"degree": degree, "college": college, "duration": duration} for degree, college, duration in zip(education_degrees, education_colleges, education_durations) if degree and college and duration]

            # Convert lists to JSON strings
            research_ids_json = json.dumps(research_ids)
            education_json = json.dumps(education)
            funding_json = json.dumps(funding_items)
            publications_json = json.dumps(publications)

            # Print values being sent to the database
            print("Updating with the following data:")
            print(f"Name: {name}, Title: {title}, Institution: {institution}, Phone: {phone}")
            print(f"Address: {address}, Website: {website}, Department: {department}")
            print(f"Profile Picture Filename: {profile_picture_filename}")
            print(f"Research Areas: {research_areas}")
            print(f"Research IDs JSON: {research_ids_json}")
            print(f"Education JSON: {education_json}")
            print(f"Funding JSON: {funding_json}")
            print(f"Publications JSON: {publications_json}")
            print(f"Career Highlights: {career_highlights}")
            print(f"Research Career: {research_career}")

            # Connect to the database and update the profile
            connection = get_db_connection()
            cursor = connection.cursor()

            update_query = """
            UPDATE details SET
                name=%s, title=%s, institution=%s, phone=%s, address=%s, website=%s,
                profile_picture=%s, department=%s, research_areas=%s, research_ids=%s,
                education=%s, funding=%s, publications=%s, career_highlights=%s, research_career=%s
            WHERE email=%s
            """
            
            cursor.execute(update_query, (
                name, title, institution, phone, address, website,
                profile_picture_filename, department, '\n'.join(research_areas), research_ids_json,
                education_json, funding_json, publications_json, '\n'.join(career_highlights),
                '\n'.join(research_career), email
            ))

            connection.commit()
            cursor.close()
            connection.close()
            
            
            
            flash('Profile updated successfully.', 'success')

            # Check the session to determine user type and redirect accordingly
            if session.get('user_type') == 'admin':
                return redirect(url_for('tables'))  # Redirect to the admin dashboard
            else:
                return redirect(url_for('profile', email=email))  # Redirect to user profile

        except Exception as e:
            return redirect(url_for('update_profile', email=email))


@app.route('/show_info/<int:id>')
def show_info(id):
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
         # Fetch color settings (Assuming there is a table named color_settings with an id of 1)
        cursor.execute("SELECT header_color, sidebar_color FROM color_settings WHERE id = 1")
        color_settings = cursor.fetchone()
        print("Color Settings:", color_settings)  # Debugging line

        # Query to get details based on ID
        query = "SELECT * FROM details WHERE id = %s"
        cursor.execute(query, (id,))
        info = cursor.fetchone()

        if info:
            # Convert JSON strings back to lists and handle possible errors
            try:
                info['research_ids'] = json.loads(info['research_ids']) if info['research_ids'] else []
            except json.JSONDecodeError as e:
                print("Error decoding research_ids:", e)
                info['research_ids'] = []

            try:
                info['education'] = json.loads(info['education']) if info['education'] else []
            except json.JSONDecodeError as e:
                print("Error decoding education:", e)
                info['education'] = []

            try:
                info['funding'] = json.loads(info['funding']) if info['funding'] else []
            except json.JSONDecodeError as e:
                print("Error decoding funding:", e)
                info['funding'] = []

            try:
                info['publications'] = json.loads(info['publications']) if info['publications'] else []
            except json.JSONDecodeError as e:
                print("Error decoding publications:", e)
                info['publications'] = []

            if info.get('career_highlights'):
                info['career_highlights'] = [item.strip() for item in info['career_highlights'].split('\n') if item.strip()]
            
            if info.get('research_career'):
                info['research_career'] = [item.strip() for item in info['research_career'].split('\n') if item.strip()]

            if info.get('research_areas'):
                info['research_areas'] = [item.strip() for item in info['research_areas'].split('\n') if item.strip()]
            
            cursor.close()
            connection.close()

            return render_template('show_info.html', info=info, colors=color_settings)
        
        else:
            flash('No information found for this ID.', 'warning')
            return redirect(url_for('profile'))
    except Error as e:
        print(f"Database error: {e}")
        flash('An error occurred while fetching data from the database.', 'danger')
        return redirect(url_for('profile'))



@app.route('/delete_details/<int:id>', methods=['POST'])
def delete_details(id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Perform the deletion
        delete_query = "DELETE FROM details WHERE id = %s"
        cursor.execute(delete_query, (id,))
        connection.commit()

        flash('Staff details deleted successfully.', 'success')
    except Error as e:
        print(f"Database error: {e}")
        flash('An error occurred while deleting data from the database.', 'danger')
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for('tables'))


@app.route('/logout', methods=['POST'])
def logout():
    # Flash a success message
    flash('Logout successful!', 'success')
    
    # Create a response object and set the cookie to expire
    response = make_response(redirect(url_for('dashboard')))
    response.set_cookie('email', '', expires=0)  # Clear the email cookie
    
    return response


if __name__ == '__main__':
    app.run(debug=True, port=5000)
