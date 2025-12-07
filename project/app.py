from flask import Flask, render_template, request
import re
from markupsafe import Markup
from fractions import Fraction
import copy
import json
import math

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/main")
def main_page():
    return render_template("main.html")

@app.route("/solve", methods=["POST"])
def solve():


    # Get form inputs
    objective = request.form.get("objective", "")
    constraint1 = request.form.get("constraint1", "")
    constraint2 = request.form.get("constraint2", "")
    nonneg = request.form.get("nonneg", "")
    
    # Detect which button was clicked
    action = request.form.get("action", "")

    def format_number(num):
        """Format number as fraction when possible, otherwise 2 decimal places"""
        if num == int(num):
            return str(int(num))
        
        try:
            frac = Fraction(num).limit_denominator(10)
            if frac.denominator != 1:
                return f"{frac.numerator}/{frac.denominator}"
            else:
                return str(frac.numerator)
        except:
            return f"{num:.2f}"

    def parse_fraction_string(value):
        """Parse fraction strings like '4/5' back to float"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            if '/' in value:
                try:
                    numerator, denominator = value.split('/')
                    return float(numerator) / float(denominator)
                except:
                    return float(value)
            else:
                try:
                    return float(value)
                except:
                    return 0.0
        return float(value)

    def format_reciprocal_display(k_value):
        """Format 1/k display properly"""
        k_str = format_number(k_value)
        
        if '/' in k_str:
            try:
                numerator, denominator = k_str.split('/')

                # For fractions, show both: 1/fraction and reciprocal
                return f"1/k = 1/{k_str} = {denominator}/{numerator}"
            except:
                return f"1/k = 1/{k_str}"
        else:

            # For whole numbers, just show 1/k directly
            return f"1/k = 1/{k_str}"

    # Variables
    standard_form = request.form.get("standard_form", "")  # Get from form if available
    tableau1 = None
    tableau_highlight = None  
    tableau_ratio = None   
    pivot_index = None
    pivot_row_index = None 
    ratio_values = None   
    show_solution_button = False
    tableau2 = None
    has_negative_in_z = None
    current_tableau_data = None
    tableau2_highlight = None
    tableau2_ratio = None
    solution1_header = None
    solution1 = None
    solution2_header = None
    solution2 = None
    solution3_header = None
    solution3 = None
    iteration_count = 1
    next_iteration = None
    show_pivotrow_button = False
    all_steps = [] 
    display_all_steps = False

    # Helper functions (moved outside to avoid duplication)
    def parse_constraint(constraint):
        if not constraint:
            return None
        s = constraint.replace(" ", "")

        try:
            m_x = re.search(r'([+-]?\d*)x', s)
            m_y = re.search(r'([+-]?\d*)y', s)
            m_rhs = re.search(r'<=([+-]?\d+)$', s)
            if not (m_x and m_y and m_rhs):
                m_alt = re.match(r'([+-]?\d*)x\+?([+-]?\d*)y<=([+-]?\d+)', s)
                if m_alt:
                    a_raw = m_alt.group(1)
                    b_raw = m_alt.group(2)
                    rhs_raw = m_alt.group(3)
                else:
                    return None
            else:
                a_raw = m_x.group(1)
                b_raw = m_y.group(1)
                rhs_raw = m_rhs.group(1)
            def to_int(raw):
                if raw in ["", "+"]:
                    return 1
                if raw == "-":
                    return -1
                return int(raw)
            a = to_int(a_raw)
            b = to_int(b_raw)
            rhs = int(rhs_raw)
            return a, b, rhs
        except Exception:
            return None

    def parse_objective(obj_str):
        if not obj_str:
            return None
        s = obj_str.replace(" ", "")
        try:
            m_x = re.search(r'([+-]?\d*)x', s)
            m_y = re.search(r'([+-]?\d*)y', s)
            def to_int(raw):
                if raw in ["", "+"]:
                    return 1
                if raw == "-":
                    return -1
                return int(raw)
            c1 = to_int(m_x.group(1)) if m_x else 0
            c2 = to_int(m_y.group(1)) if m_y else 0
            return c1, c2
        except Exception:
            return None

    def perform_pivot_operations(tableau, pivot_row, pivot_col):
        """Perform pivot operations and return new tableau with entering variable first"""
        pivot_value_str = tableau[pivot_row][pivot_col]
        pivot_value = parse_fraction_string(pivot_value_str)
        
        # Create a copy of the tableau to work with
        working_tableau = copy.deepcopy(tableau)
        
        column_names = ["B.V", "x", "y", "S₁", "S₂", "RHS"]
        pivot_var = column_names[pivot_col]
        
        # Update basic variable for pivot row - this will be the entering variable
        working_tableau[pivot_row][0] = Markup(f"<b>{pivot_var}</b>")
        
        # Normalize pivot row (divide entire row by pivot element)
        for j in range(1, len(working_tableau[0])):
            old_val_str = working_tableau[pivot_row][j]
            old_val = parse_fraction_string(old_val_str)
            new_val = old_val / pivot_value
            working_tableau[pivot_row][j] = format_number(new_val)
        
        # Update other rows (including z-row)
        for i in range(len(working_tableau)):
            if i != pivot_row:
                pivot_other_str = working_tableau[i][pivot_col]
                pivot_other = parse_fraction_string(pivot_other_str)
                
                for j in range(1, len(working_tableau[0])):
                    old_val_str = working_tableau[i][j]
                    old_val = parse_fraction_string(old_val_str)
                    pivot_row_val_str = working_tableau[pivot_row][j]
                    pivot_row_val = parse_fraction_string(pivot_row_val_str)
                    new_val = old_val - pivot_row_val * pivot_other
                    working_tableau[i][j] = format_number(new_val)
        
        # Now reorder the constraint rows so the entering variable is first
        # Keep z-row always last
        z_row = working_tableau[-1]
        constraint_rows = working_tableau[:-1]
        
        # Create new order: pivot row first, then other rows
        reordered_tableau = []
        reordered_tableau.append(working_tableau[pivot_row])  # Entering variable row first
        
        # Add other constraint rows (excluding pivot row)
        for i in range(len(constraint_rows)):
            if i != pivot_row:
                reordered_tableau.append(working_tableau[i])
        
        # Add z-row last
        reordered_tableau.append(z_row)
        
        return reordered_tableau

    def check_negative_in_z_row(tableau):
        """Check if there are negative numbers in z-row"""
        z_row = tableau[-1][1:-1]
        has_negative = any(parse_fraction_string(val) < 0 for val in z_row if val != '—')
        return has_negative

    # Handle the "solve" action - generate all steps at once
    if action == "solve":
        display_all_steps = True
        
        if objective and constraint1 and constraint2:
            # Add problem statement to all_steps
            all_steps.append({
                'type': 'problem_statement',
                'data': {
                    'objective': objective,
                    'constraint1': constraint1,
                    'constraint2': constraint2,
                    'nonneg': nonneg
                }
            })
            
            # Generate standard form
            std_obj = "Z - " + objective.replace("+", "-") + " = 0" 
            std_c1 = constraint1.replace("<=", "+ S₁ =") 
            std_c2 = constraint2.replace("<=", "+ S₂ =")  
            standard_form = f"""{std_obj}
{std_c1}
{std_c2}"""
            
            all_steps.append({
                'type': 'standard_form',
                'data': standard_form
            })
            
            parsed1 = parse_constraint(constraint1)
            parsed2 = parse_constraint(constraint2)
            
            if parsed1 is None or parsed2 is None:
                return render_template(
                    "main.html",
                    objective=objective,
                    constraint1=constraint1,
                    constraint2=constraint2,
                    nonneg=nonneg,
                    parse_error="Could not parse constraints. Use format like: 2x + 3y <= 8"
                )

            a1, b1, rhs1 = parsed1
            a2, b2, rhs2 = parsed2
            parsed_obj = parse_objective(objective)
            if parsed_obj is None:
                c1, c2 = 0, 0
            else:
                c1, c2 = parsed_obj

            # Initial Tableau
            initial_tableau = [
                [Markup("<b>S₁</b>"), a1, b1, 1, 0, rhs1],
                [Markup("<b>S₂</b>"), a2, b2, 0, 1, rhs2], 
                [Markup("<b>z</b>"), -c1, -c2, 0, 0, 0]     
            ]
            
            all_steps.append({
                'type': 'initial_tableau',
                'data': initial_tableau
            })
            
            # Start iterative process
            current_tableau = initial_tableau
            iteration = 1
            continue_iterating = True
            
            while continue_iterating:
                
                # Find pivot column for current iteration
                z_row = [parse_fraction_string(cell) for cell in current_tableau[-1][1:-1] if cell != '—']
                try:
                    min_val = min(z_row)
                    pivot_index = z_row.index(min_val) + 1
                except Exception:
                    pivot_index = 1
                
                all_steps.append({
                    'type': 'pivot_column',
                    'data': {
                        'tableau': current_tableau,
                        'pivot_index': pivot_index,
                        'iteration': iteration
                    }
                })
                
                # Find pivot row with ratios
                ratio_values = []
                for i in range(2):
                    row = current_tableau[i]
                    rhs = parse_fraction_string(row[-1])
                    pivot_col_value = parse_fraction_string(row[pivot_index]) if row[pivot_index] != '—' else 0

                    if pivot_col_value > 0:
                        ratio = rhs / pivot_col_value
                        ratio_values.append(ratio)
                    else:
                        ratio_values.append(None)

                positives = [(idx, val) for idx, val in enumerate(ratio_values) if val is not None]
                if positives:
                    pivot_idx_pair = min(positives, key=lambda t: t[1])
                    pivot_row_index = pivot_idx_pair[0]
                    k = parse_fraction_string(current_tableau[pivot_row_index][pivot_index])
                else:
                    pivot_row_index = None
                    k = None
                    for i in range(2):
                        v = parse_fraction_string(current_tableau[i][pivot_index]) if current_tableau[i][pivot_index] != '—' else 0
                        if v > 0:
                            pivot_row_index = i
                            k = v
                            break

                # Create tableau with ratios
                tableau_with_ratios = []
                for i, row in enumerate(current_tableau):
                    label = row[0]
                    if i in [0, 1]:
                        r = ratio_values[i]
                        if r is not None:
                            fraction_form = format_number(float(r))
                            rhs_display = row[-1]
                            pivot_val_display = row[pivot_index]
                            
                            if '/' in str(rhs_display) or '/' in str(pivot_val_display):
                                if float(r) == int(float(r)):
                                    ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form}"
                                else:
                                    decimal_form = f"{float(r):.2f}"
                                    ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form} ({decimal_form})"
                            else:
                                if float(r) == int(float(r)):
                                    ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form}"
                                else:
                                    decimal_form = f"{float(r):.2f}"
                                    ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form} ({decimal_form})"
                        else:
                            ratio_cell = "—"
                        new_row = [label] + row[1:] + [ratio_cell]  
                    else:
                        if k is not None:
                            k_display = format_reciprocal_display(k)
                            new_row = [label] + row[1:] + [k_display]
                        else:
                            new_row = [label] + row[1:] + ["1/k = —"]
                    tableau_with_ratios.append(new_row)

                all_steps.append({
                    'type': 'pivot_row',
                    'data': {
                        'tableau_with_ratios': tableau_with_ratios,
                        'pivot_index': pivot_index,
                        'pivot_row_index': pivot_row_index,
                        'pivot_element': current_tableau[pivot_row_index][pivot_index] if pivot_row_index is not None else None,
                        'iteration': iteration
                    }
                })
                
                # Perform pivot operations
                if pivot_row_index is not None:
                    pivot_value_str = current_tableau[pivot_row_index][pivot_index]
                    pivot_value = parse_fraction_string(pivot_value_str)
                    
                    column_names = ["B.V", "x", "y", "S₁", "S₂", "RHS"]
                    pivot_col_name = column_names[pivot_index] if pivot_index < len(column_names) else f"Col{pivot_index}"
                    
                    # Calculate reciprocal for display
                    reciprocal_display = ""
                    if pivot_value != 0:
                        reciprocal = 1 / pivot_value
                        reciprocal_display = format_number(reciprocal)
                    
                    # Solution 1: Pivot row operations
                    solution1_header = Markup(f"{current_tableau[pivot_row_index][0]}({reciprocal_display})→{pivot_col_name}") if reciprocal_display else Markup(f"{current_tableau[pivot_row_index][0]}(1/k)→{pivot_col_name}")
                    solution1 = []
                    solution1_results = []
                    
                    for j in range(1, len(current_tableau[0])):
                        old_val_str = current_tableau[pivot_row_index][j]
                        old_val = parse_fraction_string(old_val_str)
                        result = old_val / pivot_value
                        
                        if reciprocal_display:
                            solution1.append(f"{format_number(old_val)}({reciprocal_display}) = {format_number(result)}")
                        else:
                            solution1.append(f"{format_number(old_val)}(1/{format_number(pivot_value)}) = {format_number(result)}")
                        
                        solution1_results.append(result)
                    
                    # Solution 2: Other row operations
                    other_row = 1 - pivot_row_index
                    P_other_str = current_tableau[other_row][pivot_index]
                    P_other = parse_fraction_string(P_other_str)
                    
                    solution2_header = Markup(f"{current_tableau[other_row][0]} = {current_tableau[other_row][0]} - {pivot_col_name}(P {current_tableau[other_row][0]})")
                    solution2 = []
                    
                    for j in range(1, len(current_tableau[0])):
                        old_val_str = current_tableau[other_row][j]
                        old_val = parse_fraction_string(old_val_str)
                        pivot_row_result = solution1_results[j-1]
                        new_val = old_val - pivot_row_result * P_other
                        calc_str = f"{format_number(old_val)} - {format_number(pivot_row_result)}({format_number(P_other)}) = {format_number(new_val)}"
                        solution2.append(calc_str)
                    
                    # Solution 3: Z-row operations
                    P_z_str = current_tableau[2][pivot_index]
                    P_z = parse_fraction_string(P_z_str)
                    
                    solution3_header = Markup(f"z = z - {pivot_col_name}(P z)")
                    solution3 = []
                    
                    for j in range(1, len(current_tableau[0])):
                        old_val_str = current_tableau[2][j]
                        old_val = parse_fraction_string(old_val_str)
                        pivot_row_result = solution1_results[j-1]
                        new_val = old_val - pivot_row_result * P_z
                        calc_str = f"{format_number(old_val)} - {format_number(pivot_row_result)}({format_number(P_z)}) = {format_number(new_val)}"
                        solution3.append(calc_str)

                    all_steps.append({
                        'type': 'pivot_operations',
                        'data': {
                            'solution1_header': solution1_header,
                            'solution1': solution1,
                            'solution2_header': solution2_header,
                            'solution2': solution2,
                            'solution3_header': solution3_header,
                            'solution3': solution3,
                            'iteration': iteration
                        }
                    })
                    
                    # Perform pivot operation to get new tableau
                    new_tableau = perform_pivot_operations(current_tableau, pivot_row_index, pivot_index)
                    has_negative_in_z = check_negative_in_z_row(new_tableau)
                    
                    all_steps.append({
                        'type': 'new_tableau',
                        'data': {
                            'tableau': new_tableau,
                            'has_negative_in_z': has_negative_in_z,
                            'iteration_count': iteration + 1
                        }
                    })
                    
                    # Update for next iteration
                    current_tableau = new_tableau
                    iteration += 1
                    
                    # Check if we need to continue iterating
                    continue_iterating = has_negative_in_z
                else:
                    # No valid pivot row found, stop iterating
                    continue_iterating = False
            
            # Render template with all steps
            return render_template(
                "main.html",
                objective=objective,
                constraint1=constraint1,
                constraint2=constraint2,
                nonneg=nonneg,
                standard_form=standard_form,
                all_steps=all_steps,
                display_all_steps=display_all_steps
            )

    # Handle the "standard" action (kept for backward compatibility)
    if action == "standard":
        if objective and constraint1 and constraint2:
            std_obj = "Z - " + objective.replace("+", "-") + " = 0" 
            std_c1 = constraint1.replace("<=", "+ S₁ =") 
            std_c2 = constraint2.replace("<=", "+ S₂ =")  
            standard_form = f"""{std_obj}
{std_c1}
{std_c2}"""
            
            return render_template(
                "main.html",
                objective=objective,
                constraint1=constraint1,
                constraint2=constraint2,
                nonneg=nonneg,
                standard_form=standard_form,
                iteration_count=iteration_count
            )

    # Handle tableau data from iterations
    tableau_data_json = request.form.get("tableau_data")
    if tableau_data_json and tableau_data_json.strip() and tableau_data_json != "None":
        try:
            current_tableau_data = json.loads(tableau_data_json)
            # Convert back to proper format with Markup
            converted_tableau = []
            for row in current_tableau_data:
                converted_row = []
                for j, cell in enumerate(row):
                    if j == 0 and isinstance(cell, str) and ('<b>' in cell or '</b>' in cell):
                        converted_row.append(Markup(cell))
                    else:
                        converted_row.append(cell)
                converted_tableau.append(converted_row)
            current_tableau_data = converted_tableau
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON decode error: {e}")
            current_tableau_data = None
    
    # Handle different actions for iteration 2+
    if action in ["tableau2_pivotcol", "tableau2_pivotrow", "tableau2_solution"]:
        iteration_count = 2  # We're on iteration 2 or higher
    
    # Handle Pivot Column for iteration 2+
    if action == "tableau2_pivotcol":
        working_tableau = current_tableau_data
        
        # Find pivot column (highlighting)
        z_row = [parse_fraction_string(cell) for cell in working_tableau[-1][1:-1] if cell != '—']
        try:
            min_val = min(z_row)
            pivot_index = z_row.index(min_val) + 1
        except Exception:
            pivot_index = 1
        
        tableau2_highlight = working_tableau
        
        # Render template with ONLY pivot column highlighted
        return render_template(
            "main.html",
            objective=objective,
            constraint1=constraint1,
            constraint2=constraint2,
            nonneg=nonneg,
            standard_form=standard_form,  # Pass standard_form
            tableau1=tableau1,
            tableau_highlight=tableau_highlight,
            tableau2_highlight=tableau2_highlight,
            pivot_index=pivot_index,
            tableau_ratio=tableau_ratio,
            tableau2_ratio=tableau2_ratio,
            pivot_row_index=pivot_row_index,
            solution1_header=solution1_header,
            solution1=solution1,
            solution2_header=solution2_header,
            solution2=solution2,
            solution3_header=solution3_header,
            solution3=solution3,
            tableau2=tableau2,
            has_negative_in_z=has_negative_in_z,
            show_pivotrow_button=True,
            current_tableau_data=json.dumps([[str(cell) for cell in row] for row in current_tableau_data]),
            iteration_count=iteration_count
        )
    
    # Handle Pivot Row for iteration 2+
    if action == "tableau2_pivotrow":
        working_tableau = current_tableau_data
        
        # Find pivot column first
        z_row = [parse_fraction_string(cell) for cell in working_tableau[-1][1:-1] if cell != '—']
        try:
            min_val = min(z_row)
            pivot_index = z_row.index(min_val) + 1
        except Exception:
            pivot_index = 1
        
        # Calculate ratios for pivot row determination
        ratio_values = []
        for i in range(2):
            row = working_tableau[i]
            rhs = parse_fraction_string(row[-1])
            pivot_col_value = parse_fraction_string(row[pivot_index]) if row[pivot_index] != '—' else 0

            if pivot_col_value > 0:
                ratio = rhs / pivot_col_value
                ratio_values.append(ratio)
            else:
                ratio_values.append(None)

        positives = [(idx, val) for idx, val in enumerate(ratio_values) if val is not None]
        if positives:
            pivot_idx_pair = min(positives, key=lambda t: t[1])
            pivot_row_index = pivot_idx_pair[0]
            k = parse_fraction_string(working_tableau[pivot_row_index][pivot_index])
        else:
            pivot_row_index = None
            k = None
            for i in range(2):
                v = parse_fraction_string(working_tableau[i][pivot_index]) if working_tableau[i][pivot_index] != '—' else 0
                if v > 0:
                    pivot_row_index = i
                    k = v
                    break

        # Create tableau with ratios
        tableau_with_ratios = []
        for i, row in enumerate(working_tableau):
            label = row[0]
            if i in [0, 1]:
                r = ratio_values[i]
                if r is not None:
                    fraction_form = format_number(float(r))
                    # Use clearer division representation
                    rhs_display = row[-1]
                    pivot_val_display = row[pivot_index]
                    
                    # Check if either value is a fraction to avoid confusing "4/5/3" notation
                    if '/' in str(rhs_display) or '/' in str(pivot_val_display):
                        # Use division symbol for clarity
                        if float(r) == int(float(r)):
                            ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form}"
                        else:
                            decimal_form = f"{float(r):.2f}"
                            ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form} ({decimal_form})"
                    else:
                        if float(r) == int(float(r)):
                            ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form}"
                        else:
                            decimal_form = f"{float(r):.2f}"
                            ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form} ({decimal_form})"
                else:
                    ratio_cell = "—"
                new_row = [label] + row[1:] + [ratio_cell]  
            else:
                if k is not None:
                    k_display = format_reciprocal_display(k)
                    new_row = [label] + row[1:] + [k_display]
                else:
                    new_row = [label] + row[1:] + ["1/k = —"]
            tableau_with_ratios.append(new_row)

        tableau2_ratio = tableau_with_ratios
        show_solution_button = True

        return render_template(
            "main.html",
            objective=objective,
            constraint1=constraint1,
            constraint2=constraint2,
            nonneg=nonneg,
            standard_form=standard_form,  # Pass standard_form
            tableau1=tableau1,
            tableau_highlight=tableau_highlight,
            tableau2_highlight=tableau2_highlight,
            pivot_index=pivot_index,
            tableau_ratio=tableau_ratio,
            tableau2_ratio=tableau2_ratio,
            pivot_row_index=pivot_row_index,
            solution1_header=solution1_header,
            solution1=solution1,
            solution2_header=solution2_header,
            solution2=solution2,
            solution3_header=solution3_header,
            solution3=solution3,
            tableau2=tableau2,
            has_negative_in_z=has_negative_in_z,
            show_solution_button=show_solution_button,
            current_tableau_data=json.dumps([[str(cell) for cell in row] for row in current_tableau_data]),
            iteration_count=iteration_count
        )

    # Main logic for initial tableau and iteration 1 (for backward compatibility)
    if action in ["tableau1", "highlight", "pivotrow", "solution"] or action == "tableau2_solution":
        if current_tableau_data and action == "tableau2_solution":
            working_tableau = current_tableau_data
            is_iteration = True
            iteration_count = 2
        else:
            parsed1 = parse_constraint(constraint1)
            parsed2 = parse_constraint(constraint2)
            if parsed1 is None or parsed2 is None:
                return render_template(
                    "main.html",
                    objective=objective,
                    constraint1=constraint1,
                    constraint2=constraint2,
                    nonneg=nonneg,
                    standard_form=standard_form,  # Pass standard_form
                    tableau1=None,
                    parse_error="Could not parse constraints. Use format like: 2x + 3y <= 8"
                )

            a1, b1, rhs1 = parsed1
            a2, b2, rhs2 = parsed2
            parsed_obj = parse_objective(objective)
            if parsed_obj is None:
                c1, c2 = 0, 0
            else:
                c1, c2 = parsed_obj

            working_tableau = [
                [Markup("<b>S₁</b>"), a1, b1, 1, 0, rhs1],
                [Markup("<b>S₂</b>"), a2, b2, 0, 1, rhs2], 
                [Markup("<b>z</b>"), -c1, -c2, 0, 0, 0]     
            ]
            is_iteration = False
            iteration_count = 1
            tableau1 = working_tableau

        # Handle highlight step for pivotal column
        if action in ["highlight", "pivotrow", "solution", "tableau2_solution"]:
            z_row = [parse_fraction_string(cell) for cell in working_tableau[-1][1:-1] if cell != '—']
            try:
                min_val = min(z_row)
                pivot_index = z_row.index(min_val) + 1
            except Exception:
                pivot_index = 1
            
            if is_iteration:
                tableau2_highlight = working_tableau
            else:
                tableau_highlight = working_tableau

        # Handle pivot row calculation with ratios
        if action in ["pivotrow", "solution", "tableau2_solution"]:
            ratio_values = []
            for i in range(2):
                row = working_tableau[i]
                rhs = parse_fraction_string(row[-1])
                pivot_col_value = parse_fraction_string(row[pivot_index]) if row[pivot_index] != '—' else 0

                if pivot_col_value > 0:
                    ratio = rhs / pivot_col_value
                    ratio_values.append(ratio)
                else:
                    ratio_values.append(None)

            positives = [(idx, val) for idx, val in enumerate(ratio_values) if val is not None]
            if positives:
                pivot_idx_pair = min(positives, key=lambda t: t[1])
                pivot_row_index = pivot_idx_pair[0]
                k = parse_fraction_string(working_tableau[pivot_row_index][pivot_index])
            else:
                pivot_row_index = None
                k = None
                for i in range(2):
                    v = parse_fraction_string(working_tableau[i][pivot_index]) if working_tableau[i][pivot_index] != '—' else 0
                    if v > 0:
                        pivot_row_index = i
                        k = v
                        break

            tableau_with_ratios = []
            for i, row in enumerate(working_tableau):
                label = row[0]
                if i in [0, 1]:
                    r = ratio_values[i]
                    if r is not None:
                        fraction_form = format_number(float(r))
                        # Use clearer division representation
                        rhs_display = row[-1]
                        pivot_val_display = row[pivot_index]
                        
                        # Check if either value is a fraction to avoid confusing "4/5/3" notation
                        if '/' in str(rhs_display) or '/' in str(pivot_val_display):
                            # Use division symbol for clarity
                            if float(r) == int(float(r)):
                                ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form}"
                            else:
                                decimal_form = f"{float(r):.2f}"
                                ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form} ({decimal_form})"
                        else:
                            if float(r) == int(float(r)):
                                ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form}"
                            else:
                                decimal_form = f"{float(r):.2f}"
                                ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form} ({decimal_form})"
                    else:
                        ratio_cell = "—"
                    new_row = [label] + row[1:] + [ratio_cell]  
                else:
                    if k is not None:
                        k_display = format_reciprocal_display(k)
                        new_row = [label] + row[1:] + [k_display]
                    else:
                        new_row = [label] + row[1:] + ["1/k = —"]
                tableau_with_ratios.append(new_row)

            if is_iteration:
                tableau2_ratio = tableau_with_ratios
            else:
                tableau_ratio = tableau_with_ratios

            if action in ["pivotrow", "tableau2_solution"]:
                show_solution_button = True

        # PIVOT ELIMINATION
        if action in ["solution", "tableau2_solution"]:
            if pivot_index is None:
                z_row = [parse_fraction_string(cell) for cell in working_tableau[-1][1:-1] if cell != '—']
                try:
                    min_val = min(z_row)
                    pivot_index = z_row.index(min_val) + 1
                except Exception:
                    pivot_index = 1
            
            if pivot_row_index is None:
                local_ratios = []
                for i in range(2):
                    try:
                        pv = parse_fraction_string(working_tableau[i][pivot_index]) if working_tableau[i][pivot_index] != '—' else 0
                        if pv > 0:
                            local_ratios.append(parse_fraction_string(working_tableau[i][-1]) / pv)
                        else:
                            local_ratios.append(None)
                    except Exception:
                        local_ratios.append(None)
                positives_local = [(idx, val) for idx, val in enumerate(local_ratios) if val is not None]
                if positives_local:
                    pivot_row_index = int(min(positives_local, key=lambda t: t[1])[0])
                else:
                    pivot_row_index = 0

            pivot_value_str = working_tableau[pivot_row_index][pivot_index]
            pivot_value = parse_fraction_string(pivot_value_str)
            
            if pivot_value == 0:
                return render_template(
                    "main.html",
                    objective=objective,
                    constraint1=constraint1,
                    constraint2=constraint2,
                    nonneg=nonneg,
                    standard_form=standard_form,  # Pass standard_form
                    tableau1=tableau1,
                    tableau_highlight=tableau_highlight,
                    pivot_index=pivot_index,
                    tableau_ratio=tableau_ratio,
                    pivot_row_index=pivot_row_index,
                    solution_error="Pivot element is zero (cannot divide)."
                )

            # SOLUTIONS
            column_names = ["B.V", "x", "y", "S₁", "S₂", "RHS"]
            pivot_col_name = column_names[pivot_index] if pivot_index < len(column_names) else f"Col{pivot_index}"
            
            # Calculate reciprocal for display
            reciprocal_display = ""
            if pivot_value != 0:
                reciprocal = 1 / pivot_value
                reciprocal_display = format_number(reciprocal)
            
            # Use Markup to allow HTML in solution headers - FIXED to show reciprocal
            if reciprocal_display:
                solution1_header = Markup(f"{working_tableau[pivot_row_index][0]}({reciprocal_display})→{pivot_col_name}")
            else:
                solution1_header = Markup(f"{working_tableau[pivot_row_index][0]}(1/k)→{pivot_col_name}")
            
            solution1 = []
            solution1_results = []
            
            for j in range(1, len(working_tableau[0])):
                old_val_str = working_tableau[pivot_row_index][j]
                old_val = parse_fraction_string(old_val_str)
                result = old_val / pivot_value
                
                # FIXED: Show the actual reciprocal, not "1/k"
                if reciprocal_display:
                    solution1.append(f"{format_number(old_val)}({reciprocal_display}) = {format_number(result)}")
                else:
                    solution1.append(f"{format_number(old_val)}(1/{format_number(pivot_value)}) = {format_number(result)}")
                
                solution1_results.append(result)
            
            other_row = 1 - pivot_row_index
            P_other_str = working_tableau[other_row][pivot_index]
            P_other = parse_fraction_string(P_other_str)
            
            solution2_header = Markup(f"{working_tableau[other_row][0]} = {working_tableau[other_row][0]} - {pivot_col_name}(P {working_tableau[other_row][0]})")
            solution2 = []
            
            for j in range(1, len(working_tableau[0])):
                old_val_str = working_tableau[other_row][j]
                old_val = parse_fraction_string(old_val_str)
                pivot_row_result = solution1_results[j-1]
                new_val = old_val - pivot_row_result * P_other
                calc_str = f"{format_number(old_val)} - {format_number(pivot_row_result)}({format_number(P_other)}) = {format_number(new_val)}"
                solution2.append(calc_str)
            
            P_z_str = working_tableau[2][pivot_index]
            P_z = parse_fraction_string(P_z_str)
            
            solution3_header = Markup(f"z = z - {pivot_col_name}(P z)")
            solution3 = []
            
            for j in range(1, len(working_tableau[0])):
                old_val_str = working_tableau[2][j]
                old_val = parse_fraction_string(old_val_str)
                pivot_row_result = solution1_results[j-1]
                new_val = old_val - pivot_row_result * P_z
                calc_str = f"{format_number(old_val)} - {format_number(pivot_row_result)}({format_number(P_z)}) = {format_number(new_val)}"
                solution3.append(calc_str)

            new_tableau = perform_pivot_operations(working_tableau, pivot_row_index, pivot_index)
            has_negative_in_z = check_negative_in_z_row(new_tableau)

            # Determine next iteration count
            if is_iteration:
                tableau2 = new_tableau
                next_iteration = iteration_count + 1
            else:
                tableau2 = new_tableau
                next_iteration = 2

            return render_template(
                "main.html",
                objective=objective,
                constraint1=constraint1,
                constraint2=constraint2,
                nonneg=nonneg,
                standard_form=standard_form,  # Pass standard_form
                tableau1=tableau1,
                tableau_highlight=tableau_highlight,
                tableau2_highlight=tableau2_highlight,
                pivot_index=pivot_index,
                tableau_ratio=tableau_ratio,
                tableau2_ratio=tableau2_ratio,
                pivot_row_index=pivot_row_index,
                solution1_header=solution1_header,
                solution1=solution1,
                solution2_header=solution2_header,
                solution2=solution2,
                solution3_header=solution3_header,
                solution3=solution3,
                tableau2=tableau2,
                has_negative_in_z=has_negative_in_z,
                show_solution_button=True,
                current_tableau_data=json.dumps([[str(cell) for cell in row] for row in new_tableau]) if new_tableau else None,
                iteration_count=iteration_count,
                next_iteration=next_iteration
            )

    # Render template with all variables (for backward compatibility)
    return render_template(
        "main.html",
        objective=objective,
        constraint1=constraint1,
        constraint2=constraint2,
        nonneg=nonneg,
        standard_form=standard_form,
        tableau1=tableau1,
        tableau_highlight=tableau_highlight,
        tableau2_highlight=tableau2_highlight,
        pivot_index=pivot_index,
        tableau_ratio=tableau_ratio,   
        tableau2_ratio=tableau2_ratio,
        pivot_row_index=pivot_row_index,
        solution1_header=solution1_header,
        solution1=solution1,
        solution2_header=solution2_header,
        solution2=solution2,
        solution3_header=solution3_header,
        solution3=solution3,
        show_solution_button=show_solution_button,
        show_pivotrow_button=show_pivotrow_button,
        tableau2=tableau2,
        has_negative_in_z=has_negative_in_z,
        current_tableau_data=current_tableau_data,
        iteration_count=iteration_count,      
        next_iteration=next_iteration,
        all_steps=all_steps,
        display_all_steps=display_all_steps
    )

# ==================== ADDED ABOUT ROUTE ====================
@app.route("/about")
def about_page():
    return render_template("about.html")
# ===========================================================


if __name__ == "__main__":
    app.run(debug=True)




# from flask import Flask, render_template, request
# import re
# from markupsafe import Markup
# from fractions import Fraction
# import copy
# import json
# import math

# app = Flask(__name__)

# @app.route("/")
# def home():
#     return render_template("index.html")

# @app.route("/main")
# def main_page():
#     return render_template("main.html")

# @app.route("/solve", methods=["POST"])
# def solve():

#     # Get form inputs
#     objective = request.form.get("objective", "")
#     constraint1 = request.form.get("constraint1", "")
#     constraint2 = request.form.get("constraint2", "")
#     nonneg = request.form.get("nonneg", "")
    
#     # Detect which button was clicked
#     action = request.form.get("action", "")

#     def format_number(num):
#         """Format number as fraction when possible, otherwise 2 decimal places"""
#         if num == int(num):
#             return str(int(num))
        
#         try:
#             frac = Fraction(num).limit_denominator(10)
#             if frac.denominator != 1:
#                 return f"{frac.numerator}/{frac.denominator}"
#             else:
#                 return str(frac.numerator)
#         except:
#             return f"{num:.2f}"

#     def parse_fraction_string(value):
#         """Parse fraction strings like '4/5' back to float"""
#         if isinstance(value, (int, float)):
#             return float(value)
#         if isinstance(value, str):
#             if '/' in value:
#                 try:
#                     numerator, denominator = value.split('/')
#                     return float(numerator) / float(denominator)
#                 except:
#                     return float(value)
#             else:
#                 try:
#                     return float(value)
#                 except:
#                     return 0.0
#         return float(value)

#     def format_reciprocal_display(k_value):
#         """Format 1/k display properly"""
#         k_str = format_number(k_value)
        
#         if '/' in k_str:
#             try:
#                 numerator, denominator = k_str.split('/')

#                 # For fractions, show both: 1/fraction and reciprocal
#                 return f"1/k = 1/{k_str} = {denominator}/{numerator}"
#             except:
#                 return f"1/k = 1/{k_str}"
#         else:

#             # For whole numbers, just show 1/k directly
#             return f"1/k = 1/{k_str}"

#     # Variables
#     standard_form = request.form.get("standard_form", "")  # Get from form if available
#     tableau1 = None
#     tableau_highlight = None  
#     tableau_ratio = None   
#     pivot_index = None
#     pivot_row_index = None 
#     ratio_values = None   
#     show_solution_button = False
#     tableau2 = None
#     has_negative_in_z = None
#     current_tableau_data = None
#     tableau2_highlight = None
#     tableau2_ratio = None
#     solution1_header = None
#     solution1 = None
#     solution2_header = None
#     solution2 = None
#     solution3_header = None
#     solution3 = None
#     iteration_count = 1
#     next_iteration = None
#     show_pivotrow_button = False
#     all_steps = [] 
#     display_all_steps = False

#     # Helper functions (moved outside to avoid duplication)
#     def parse_constraint(constraint):
#         if not constraint:
#             return None
#         s = constraint.replace(" ", "")

#         try:
#             m_x = re.search(r'([+-]?\d*)x', s)
#             m_y = re.search(r'([+-]?\d*)y', s)
#             m_rhs = re.search(r'<=([+-]?\d+)$', s)
#             if not (m_x and m_y and m_rhs):
#                 m_alt = re.match(r'([+-]?\d*)x\+?([+-]?\d*)y<=([+-]?\d+)', s)
#                 if m_alt:
#                     a_raw = m_alt.group(1)
#                     b_raw = m_alt.group(2)
#                     rhs_raw = m_alt.group(3)
#                 else:
#                     return None
#             else:
#                 a_raw = m_x.group(1)
#                 b_raw = m_y.group(1)
#                 rhs_raw = m_rhs.group(1)
#             def to_int(raw):
#                 if raw in ["", "+"]:
#                     return 1
#                 if raw == "-":
#                     return -1
#                 return int(raw)
#             a = to_int(a_raw)
#             b = to_int(b_raw)
#             rhs = int(rhs_raw)
#             return a, b, rhs
#         except Exception:
#             return None

#     def parse_objective(obj_str):
#         if not obj_str:
#             return None
#         s = obj_str.replace(" ", "")
#         try:
#             m_x = re.search(r'([+-]?\d*)x', s)
#             m_y = re.search(r'([+-]?\d*)y', s)
#             def to_int(raw):
#                 if raw in ["", "+"]:
#                     return 1
#                 if raw == "-":
#                     return -1
#                 return int(raw)
#             c1 = to_int(m_x.group(1)) if m_x else 0
#             c2 = to_int(m_y.group(1)) if m_y else 0
#             return c1, c2
#         except Exception:
#             return None

#     def perform_pivot_operations(tableau, pivot_row, pivot_col):
#         """Perform pivot operations and return new tableau with entering variable first"""
#         pivot_value_str = tableau[pivot_row][pivot_col]
#         pivot_value = parse_fraction_string(pivot_value_str)
        
#         # Create a copy of the tableau to work with
#         working_tableau = copy.deepcopy(tableau)
        
#         column_names = ["B.V", "x", "y", "S₁", "S₂", "RHS"]
#         pivot_var = column_names[pivot_col]
        
#         # Update basic variable for pivot row - this will be the entering variable
#         working_tableau[pivot_row][0] = Markup(f"<b>{pivot_var}</b>")
        
#         # Normalize pivot row (divide entire row by pivot element)
#         for j in range(1, len(working_tableau[0])):
#             old_val_str = working_tableau[pivot_row][j]
#             old_val = parse_fraction_string(old_val_str)
#             new_val = old_val / pivot_value
#             working_tableau[pivot_row][j] = format_number(new_val)
        
#         # Update other rows (including z-row)
#         for i in range(len(working_tableau)):
#             if i != pivot_row:
#                 pivot_other_str = working_tableau[i][pivot_col]
#                 pivot_other = parse_fraction_string(pivot_other_str)
                
#                 for j in range(1, len(working_tableau[0])):
#                     old_val_str = working_tableau[i][j]
#                     old_val = parse_fraction_string(old_val_str)
#                     pivot_row_val_str = working_tableau[pivot_row][j]
#                     pivot_row_val = parse_fraction_string(pivot_row_val_str)
#                     new_val = old_val - pivot_row_val * pivot_other
#                     working_tableau[i][j] = format_number(new_val)
        
#         # Now reorder the constraint rows so the entering variable is first
#         # Keep z-row always last
#         z_row = working_tableau[-1]
#         constraint_rows = working_tableau[:-1]
        
#         # Create new order: pivot row first, then other rows
#         reordered_tableau = []
#         reordered_tableau.append(working_tableau[pivot_row])  # Entering variable row first
        
#         # Add other constraint rows (excluding pivot row)
#         for i in range(len(constraint_rows)):
#             if i != pivot_row:
#                 reordered_tableau.append(working_tableau[i])
        
#         # Add z-row last
#         reordered_tableau.append(z_row)
        
#         return reordered_tableau

#     def check_negative_in_z_row(tableau):
#         """Check if there are negative numbers in z-row"""
#         z_row = tableau[-1][1:-1]
#         has_negative = any(parse_fraction_string(val) < 0 for val in z_row if val != '—')
#         return has_negative

#     # Handle the "solve" action - generate all steps at once
#     if action == "solve":
#         display_all_steps = True
        
#         if objective and constraint1 and constraint2:
#             # Add problem statement to all_steps
#             all_steps.append({
#                 'type': 'problem_statement',
#                 'data': {
#                     'objective': objective,
#                     'constraint1': constraint1,
#                     'constraint2': constraint2,
#                     'nonneg': nonneg
#                 }
#             })
            
#             # Generate standard form
#             std_obj = "Z - " + objective.replace("+", "-") + " = 0" 
#             std_c1 = constraint1.replace("<=", "+ S₁ =") 
#             std_c2 = constraint2.replace("<=", "+ S₂ =")  
#             standard_form = f"""{std_obj}
# {std_c1}
# {std_c2}"""
            
#             all_steps.append({
#                 'type': 'standard_form',
#                 'data': standard_form
#             })
            
#             parsed1 = parse_constraint(constraint1)
#             parsed2 = parse_constraint(constraint2)
            
#             if parsed1 is None or parsed2 is None:
#                 return render_template(
#                     "main.html",
#                     objective=objective,
#                     constraint1=constraint1,
#                     constraint2=constraint2,
#                     nonneg=nonneg,
#                     parse_error="Could not parse constraints. Use format like: 2x + 3y <= 8"
#                 )

#             a1, b1, rhs1 = parsed1
#             a2, b2, rhs2 = parsed2
#             parsed_obj = parse_objective(objective)
#             if parsed_obj is None:
#                 c1, c2 = 0, 0
#             else:
#                 c1, c2 = parsed_obj

#             # Initial Tableau
#             initial_tableau = [
#                 [Markup("<b>S₁</b>"), a1, b1, 1, 0, rhs1],
#                 [Markup("<b>S₂</b>"), a2, b2, 0, 1, rhs2], 
#                 [Markup("<b>z</b>"), -c1, -c2, 0, 0, 0]     
#             ]
            
#             all_steps.append({
#                 'type': 'initial_tableau',
#                 'data': initial_tableau
#             })
            
#             # Start iterative process
#             current_tableau = initial_tableau
#             iteration = 1
#             continue_iterating = True
            
#             while continue_iterating:
                
#                 # Find pivot column for current iteration
#                 z_row = [parse_fraction_string(cell) for cell in current_tableau[-1][1:-1] if cell != '—']
#                 try:
#                     min_val = min(z_row)
#                     pivot_index = z_row.index(min_val) + 1
#                 except Exception:
#                     pivot_index = 1
                
#                 all_steps.append({
#                     'type': 'pivot_column',
#                     'data': {
#                         'tableau': current_tableau,
#                         'pivot_index': pivot_index,
#                         'iteration': iteration
#                     }
#                 })
                
#                 # Find pivot row with ratios
#                 ratio_values = []
#                 for i in range(2):
#                     row = current_tableau[i]
#                     rhs = parse_fraction_string(row[-1])
#                     pivot_col_value = parse_fraction_string(row[pivot_index]) if row[pivot_index] != '—' else 0

#                     if pivot_col_value > 0:
#                         ratio = rhs / pivot_col_value
#                         ratio_values.append(ratio)
#                     else:
#                         ratio_values.append(None)

#                 positives = [(idx, val) for idx, val in enumerate(ratio_values) if val is not None]
#                 if positives:
#                     pivot_idx_pair = min(positives, key=lambda t: t[1])
#                     pivot_row_index = pivot_idx_pair[0]
#                     k = parse_fraction_string(current_tableau[pivot_row_index][pivot_index])
#                 else:
#                     pivot_row_index = None
#                     k = None
#                     for i in range(2):
#                         v = parse_fraction_string(current_tableau[i][pivot_index]) if current_tableau[i][pivot_index] != '—' else 0
#                         if v > 0:
#                             pivot_row_index = i
#                             k = v
#                             break

#                 # Create tableau with ratios
#                 tableau_with_ratios = []
#                 for i, row in enumerate(current_tableau):
#                     label = row[0]
#                     if i in [0, 1]:
#                         r = ratio_values[i]
#                         if r is not None:
#                             fraction_form = format_number(float(r))
#                             rhs_display = row[-1]
#                             pivot_val_display = row[pivot_index]
                            
#                             if '/' in str(rhs_display) or '/' in str(pivot_val_display):
#                                 if float(r) == int(float(r)):
#                                     ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form}"
#                                 else:
#                                     decimal_form = f"{float(r):.2f}"
#                                     ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form} ({decimal_form})"
#                             else:
#                                 if float(r) == int(float(r)):
#                                     ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form}"
#                                 else:
#                                     decimal_form = f"{float(r):.2f}"
#                                     ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form} ({decimal_form})"
#                         else:
#                             ratio_cell = "—"
#                         new_row = [label] + row[1:] + [ratio_cell]  
#                     else:
#                         if k is not None:
#                             k_display = format_reciprocal_display(k)
#                             new_row = [label] + row[1:] + [k_display]
#                         else:
#                             new_row = [label] + row[1:] + ["1/k = —"]
#                     tableau_with_ratios.append(new_row)

#                 all_steps.append({
#                     'type': 'pivot_row',
#                     'data': {
#                         'tableau_with_ratios': tableau_with_ratios,
#                         'pivot_index': pivot_index,
#                         'pivot_row_index': pivot_row_index,
#                         'pivot_element': current_tableau[pivot_row_index][pivot_index] if pivot_row_index is not None else None,
#                         'iteration': iteration
#                     }
#                 })
                
#                 # Perform pivot operations
#                 if pivot_row_index is not None:
#                     pivot_value_str = current_tableau[pivot_row_index][pivot_index]
#                     pivot_value = parse_fraction_string(pivot_value_str)
                    
#                     column_names = ["B.V", "x", "y", "S₁", "S₂", "RHS"]
#                     pivot_col_name = column_names[pivot_index] if pivot_index < len(column_names) else f"Col{pivot_index}"
                    
#                     # Calculate reciprocal for display
#                     reciprocal_display = ""
#                     if pivot_value != 0:
#                         reciprocal = 1 / pivot_value
#                         reciprocal_display = format_number(reciprocal)
                    
#                     # Solution 1: Pivot row operations
#                     solution1_header = Markup(f"{current_tableau[pivot_row_index][0]}({reciprocal_display})→{pivot_col_name}") if reciprocal_display else Markup(f"{current_tableau[pivot_row_index][0]}(1/k)→{pivot_col_name}")
#                     solution1 = []
#                     solution1_results = []
                    
#                     for j in range(1, len(current_tableau[0])):
#                         old_val_str = current_tableau[pivot_row_index][j]
#                         old_val = parse_fraction_string(old_val_str)
#                         result = old_val / pivot_value
                        
#                         if reciprocal_display:
#                             solution1.append(f"{format_number(old_val)}({reciprocal_display}) = {format_number(result)}")
#                         else:
#                             solution1.append(f"{format_number(old_val)}(1/{format_number(pivot_value)}) = {format_number(result)}")
                        
#                         solution1_results.append(result)
                    
#                     # Solution 2: Other row operations
#                     other_row = 1 - pivot_row_index
#                     P_other_str = current_tableau[other_row][pivot_index]
#                     P_other = parse_fraction_string(P_other_str)
                    
#                     solution2_header = Markup(f"{current_tableau[other_row][0]} = {current_tableau[other_row][0]} - {pivot_col_name}(P {current_tableau[other_row][0]})")
#                     solution2 = []
                    
#                     for j in range(1, len(current_tableau[0])):
#                         old_val_str = current_tableau[other_row][j]
#                         old_val = parse_fraction_string(old_val_str)
#                         pivot_row_result = solution1_results[j-1]
#                         new_val = old_val - pivot_row_result * P_other
#                         calc_str = f"{format_number(old_val)} - {format_number(pivot_row_result)}({format_number(P_other)}) = {format_number(new_val)}"
#                         solution2.append(calc_str)
                    
#                     # Solution 3: Z-row operations
#                     P_z_str = current_tableau[2][pivot_index]
#                     P_z = parse_fraction_string(P_z_str)
                    
#                     solution3_header = Markup(f"z = z - {pivot_col_name}(P z)")
#                     solution3 = []
                    
#                     for j in range(1, len(current_tableau[0])):
#                         old_val_str = current_tableau[2][j]
#                         old_val = parse_fraction_string(old_val_str)
#                         pivot_row_result = solution1_results[j-1]
#                         new_val = old_val - pivot_row_result * P_z
#                         calc_str = f"{format_number(old_val)} - {format_number(pivot_row_result)}({format_number(P_z)}) = {format_number(new_val)}"
#                         solution3.append(calc_str)

#                     all_steps.append({
#                         'type': 'pivot_operations',
#                         'data': {
#                             'solution1_header': solution1_header,
#                             'solution1': solution1,
#                             'solution2_header': solution2_header,
#                             'solution2': solution2,
#                             'solution3_header': solution3_header,
#                             'solution3': solution3,
#                             'iteration': iteration
#                         }
#                     })
                    
#                     # Perform pivot operation to get new tableau
#                     new_tableau = perform_pivot_operations(current_tableau, pivot_row_index, pivot_index)
#                     has_negative_in_z = check_negative_in_z_row(new_tableau)
                    
#                     all_steps.append({
#                         'type': 'new_tableau',
#                         'data': {
#                             'tableau': new_tableau,
#                             'has_negative_in_z': has_negative_in_z,
#                             'iteration_count': iteration + 1
#                         }
#                     })
                    
#                     # Update for next iteration
#                     current_tableau = new_tableau
#                     iteration += 1
                    
#                     # Check if we need to continue iterating
#                     continue_iterating = has_negative_in_z
#                 else:
#                     # No valid pivot row found, stop iterating
#                     continue_iterating = False
            
#             # Render template with all steps
#             return render_template(
#                 "main.html",
#                 objective=objective,
#                 constraint1=constraint1,
#                 constraint2=constraint2,
#                 nonneg=nonneg,
#                 standard_form=standard_form,
#                 all_steps=all_steps,
#                 display_all_steps=display_all_steps
#             )

#     # Handle the "standard" action (kept for backward compatibility)
#     if action == "standard":
#         if objective and constraint1 and constraint2:
#             std_obj = "Z - " + objective.replace("+", "-") + " = 0" 
#             std_c1 = constraint1.replace("<=", "+ S₁ =") 
#             std_c2 = constraint2.replace("<=", "+ S₂ =")  
#             standard_form = f"""{std_obj}
# {std_c1}
# {std_c2}"""
            
#             return render_template(
#                 "main.html",
#                 objective=objective,
#                 constraint1=constraint1,
#                 constraint2=constraint2,
#                 nonneg=nonneg,
#                 standard_form=standard_form,
#                 iteration_count=iteration_count
#             )

#     # Handle tableau data from iterations
#     tableau_data_json = request.form.get("tableau_data")
#     if tableau_data_json and tableau_data_json.strip() and tableau_data_json != "None":
#         try:
#             current_tableau_data = json.loads(tableau_data_json)
#             # Convert back to proper format with Markup
#             converted_tableau = []
#             for row in current_tableau_data:
#                 converted_row = []
#                 for j, cell in enumerate(row):
#                     if j == 0 and isinstance(cell, str) and ('<b>' in cell or '</b>' in cell):
#                         converted_row.append(Markup(cell))
#                     else:
#                         converted_row.append(cell)
#                 converted_tableau.append(converted_row)
#             current_tableau_data = converted_tableau
#         except (json.JSONDecodeError, ValueError) as e:
#             print(f"JSON decode error: {e}")
#             current_tableau_data = None
    
#     # Handle different actions for iteration 2+
#     if action in ["tableau2_pivotcol", "tableau2_pivotrow", "tableau2_solution"]:
#         iteration_count = 2  # We're on iteration 2 or higher
    
#     # Handle Pivot Column for iteration 2+
#     if action == "tableau2_pivotcol":
#         working_tableau = current_tableau_data
        
#         # Find pivot column (highlighting)
#         z_row = [parse_fraction_string(cell) for cell in working_tableau[-1][1:-1] if cell != '—']
#         try:
#             min_val = min(z_row)
#             pivot_index = z_row.index(min_val) + 1
#         except Exception:
#             pivot_index = 1
        
#         tableau2_highlight = working_tableau
        
#         # Render template with ONLY pivot column highlighted
#         return render_template(
#             "main.html",
#             objective=objective,
#             constraint1=constraint1,
#             constraint2=constraint2,
#             nonneg=nonneg,
#             standard_form=standard_form,  # Pass standard_form
#             tableau1=tableau1,
#             tableau_highlight=tableau_highlight,
#             tableau2_highlight=tableau2_highlight,
#             pivot_index=pivot_index,
#             tableau_ratio=tableau_ratio,
#             tableau2_ratio=tableau2_ratio,
#             pivot_row_index=pivot_row_index,
#             solution1_header=solution1_header,
#             solution1=solution1,
#             solution2_header=solution2_header,
#             solution2=solution2,
#             solution3_header=solution3_header,
#             solution3=solution3,
#             tableau2=tableau2,
#             has_negative_in_z=has_negative_in_z,
#             show_pivotrow_button=True,
#             current_tableau_data=json.dumps([[str(cell) for cell in row] for row in current_tableau_data]),
#             iteration_count=iteration_count
#         )
    
#     # Handle Pivot Row for iteration 2+
#     if action == "tableau2_pivotrow":
#         working_tableau = current_tableau_data
        
#         # Find pivot column first
#         z_row = [parse_fraction_string(cell) for cell in working_tableau[-1][1:-1] if cell != '—']
#         try:
#             min_val = min(z_row)
#             pivot_index = z_row.index(min_val) + 1
#         except Exception:
#             pivot_index = 1
        
#         # Calculate ratios for pivot row determination
#         ratio_values = []
#         for i in range(2):
#             row = working_tableau[i]
#             rhs = parse_fraction_string(row[-1])
#             pivot_col_value = parse_fraction_string(row[pivot_index]) if row[pivot_index] != '—' else 0

#             if pivot_col_value > 0:
#                 ratio = rhs / pivot_col_value
#                 ratio_values.append(ratio)
#             else:
#                 ratio_values.append(None)

#         positives = [(idx, val) for idx, val in enumerate(ratio_values) if val is not None]
#         if positives:
#             pivot_idx_pair = min(positives, key=lambda t: t[1])
#             pivot_row_index = pivot_idx_pair[0]
#             k = parse_fraction_string(working_tableau[pivot_row_index][pivot_index])
#         else:
#             pivot_row_index = None
#             k = None
#             for i in range(2):
#                 v = parse_fraction_string(working_tableau[i][pivot_index]) if working_tableau[i][pivot_index] != '—' else 0
#                 if v > 0:
#                     pivot_row_index = i
#                     k = v
#                     break

#         # Create tableau with ratios
#         tableau_with_ratios = []
#         for i, row in enumerate(working_tableau):
#             label = row[0]
#             if i in [0, 1]:
#                 r = ratio_values[i]
#                 if r is not None:
#                     fraction_form = format_number(float(r))
#                     # Use clearer division representation
#                     rhs_display = row[-1]
#                     pivot_val_display = row[pivot_index]
                    
#                     # Check if either value is a fraction to avoid confusing "4/5/3" notation
#                     if '/' in str(rhs_display) or '/' in str(pivot_val_display):
#                         # Use division symbol for clarity
#                         if float(r) == int(float(r)):
#                             ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form}"
#                         else:
#                             decimal_form = f"{float(r):.2f}"
#                             ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form} ({decimal_form})"
#                     else:
#                         if float(r) == int(float(r)):
#                             ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form}"
#                         else:
#                             decimal_form = f"{float(r):.2f}"
#                             ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form} ({decimal_form})"
#                 else:
#                     ratio_cell = "—"
#                 new_row = [label] + row[1:] + [ratio_cell]  
#             else:
#                 if k is not None:
#                     k_display = format_reciprocal_display(k)
#                     new_row = [label] + row[1:] + [k_display]
#                 else:
#                     new_row = [label] + row[1:] + ["1/k = —"]
#             tableau_with_ratios.append(new_row)

#         tableau2_ratio = tableau_with_ratios
#         show_solution_button = True

#         return render_template(
#             "main.html",
#             objective=objective,
#             constraint1=constraint1,
#             constraint2=constraint2,
#             nonneg=nonneg,
#             standard_form=standard_form,  # Pass standard_form
#             tableau1=tableau1,
#             tableau_highlight=tableau_highlight,
#             tableau2_highlight=tableau2_highlight,
#             pivot_index=pivot_index,
#             tableau_ratio=tableau_ratio,
#             tableau2_ratio=tableau2_ratio,
#             pivot_row_index=pivot_row_index,
#             solution1_header=solution1_header,
#             solution1=solution1,
#             solution2_header=solution2_header,
#             solution2=solution2,
#             solution3_header=solution3_header,
#             solution3=solution3,
#             tableau2=tableau2,
#             has_negative_in_z=has_negative_in_z,
#             show_solution_button=show_solution_button,
#             current_tableau_data=json.dumps([[str(cell) for cell in row] for row in current_tableau_data]),
#             iteration_count=iteration_count
#         )

#     # Main logic for initial tableau and iteration 1 (for backward compatibility)
#     if action in ["tableau1", "highlight", "pivotrow", "solution"] or action == "tableau2_solution":
#         if current_tableau_data and action == "tableau2_solution":
#             working_tableau = current_tableau_data
#             is_iteration = True
#             iteration_count = 2
#         else:
#             parsed1 = parse_constraint(constraint1)
#             parsed2 = parse_constraint(constraint2)
#             if parsed1 is None or parsed2 is None:
#                 return render_template(
#                     "main.html",
#                     objective=objective,
#                     constraint1=constraint1,
#                     constraint2=constraint2,
#                     nonneg=nonneg,
#                     standard_form=standard_form,  # Pass standard_form
#                     tableau1=None,
#                     parse_error="Could not parse constraints. Use format like: 2x + 3y <= 8"
#                 )

#             a1, b1, rhs1 = parsed1
#             a2, b2, rhs2 = parsed2
#             parsed_obj = parse_objective(objective)
#             if parsed_obj is None:
#                 c1, c2 = 0, 0
#             else:
#                 c1, c2 = parsed_obj

#             working_tableau = [
#                 [Markup("<b>S₁</b>"), a1, b1, 1, 0, rhs1],
#                 [Markup("<b>S₂</b>"), a2, b2, 0, 1, rhs2], 
#                 [Markup("<b>z</b>"), -c1, -c2, 0, 0, 0]     
#             ]
#             is_iteration = False
#             iteration_count = 1
#             tableau1 = working_tableau

#         # Handle highlight step for pivotal column
#         if action in ["highlight", "pivotrow", "solution", "tableau2_solution"]:
#             z_row = [parse_fraction_string(cell) for cell in working_tableau[-1][1:-1] if cell != '—']
#             try:
#                 min_val = min(z_row)
#                 pivot_index = z_row.index(min_val) + 1
#             except Exception:
#                 pivot_index = 1
            
#             if is_iteration:
#                 tableau2_highlight = working_tableau
#             else:
#                 tableau_highlight = working_tableau

#         # Handle pivot row calculation with ratios
#         if action in ["pivotrow", "solution", "tableau2_solution"]:
#             ratio_values = []
#             for i in range(2):
#                 row = working_tableau[i]
#                 rhs = parse_fraction_string(row[-1])
#                 pivot_col_value = parse_fraction_string(row[pivot_index]) if row[pivot_index] != '—' else 0

#                 if pivot_col_value > 0:
#                     ratio = rhs / pivot_col_value
#                     ratio_values.append(ratio)
#                 else:
#                     ratio_values.append(None)

#             positives = [(idx, val) for idx, val in enumerate(ratio_values) if val is not None]
#             if positives:
#                 pivot_idx_pair = min(positives, key=lambda t: t[1])
#                 pivot_row_index = pivot_idx_pair[0]
#                 k = parse_fraction_string(working_tableau[pivot_row_index][pivot_index])
#             else:
#                 pivot_row_index = None
#                 k = None
#                 for i in range(2):
#                     v = parse_fraction_string(working_tableau[i][pivot_index]) if working_tableau[i][pivot_index] != '—' else 0
#                     if v > 0:
#                         pivot_row_index = i
#                         k = v
#                         break

#             tableau_with_ratios = []
#             for i, row in enumerate(working_tableau):
#                 label = row[0]
#                 if i in [0, 1]:
#                     r = ratio_values[i]
#                     if r is not None:
#                         fraction_form = format_number(float(r))
#                         # Use clearer division representation
#                         rhs_display = row[-1]
#                         pivot_val_display = row[pivot_index]
                        
#                         # Check if either value is a fraction to avoid confusing "4/5/3" notation
#                         if '/' in str(rhs_display) or '/' in str(pivot_val_display):
#                             # Use division symbol for clarity
#                             if float(r) == int(float(r)):
#                                 ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form}"
#                             else:
#                                 decimal_form = f"{float(r):.2f}"
#                                 ratio_cell = f"{rhs_display} ÷ {pivot_val_display} = {fraction_form} ({decimal_form})"
#                         else:
#                             if float(r) == int(float(r)):
#                                 ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form}"
#                             else:
#                                 decimal_form = f"{float(r):.2f}"
#                                 ratio_cell = f"{rhs_display}/{pivot_val_display} = {fraction_form} ({decimal_form})"
#                     else:
#                         ratio_cell = "—"
#                     new_row = [label] + row[1:] + [ratio_cell]  
#                 else:
#                     if k is not None:
#                         k_display = format_reciprocal_display(k)
#                         new_row = [label] + row[1:] + [k_display]
#                     else:
#                         new_row = [label] + row[1:] + ["1/k = —"]
#                 tableau_with_ratios.append(new_row)

#             if is_iteration:
#                 tableau2_ratio = tableau_with_ratios
#             else:
#                 tableau_ratio = tableau_with_ratios

#             if action in ["pivotrow", "tableau2_solution"]:
#                 show_solution_button = True

#         # PIVOT ELIMINATION
#         if action in ["solution", "tableau2_solution"]:
#             if pivot_index is None:
#                 z_row = [parse_fraction_string(cell) for cell in working_tableau[-1][1:-1] if cell != '—']
#                 try:
#                     min_val = min(z_row)
#                     pivot_index = z_row.index(min_val) + 1
#                 except Exception:
#                     pivot_index = 1
            
#             if pivot_row_index is None:
#                 local_ratios = []
#                 for i in range(2):
#                     try:
#                         pv = parse_fraction_string(working_tableau[i][pivot_index]) if working_tableau[i][pivot_index] != '—' else 0
#                         if pv > 0:
#                             local_ratios.append(parse_fraction_string(working_tableau[i][-1]) / pv)
#                         else:
#                             local_ratios.append(None)
#                     except Exception:
#                         local_ratios.append(None)
#                 positives_local = [(idx, val) for idx, val in enumerate(local_ratios) if val is not None]
#                 if positives_local:
#                     pivot_row_index = int(min(positives_local, key=lambda t: t[1])[0])
#                 else:
#                     pivot_row_index = 0

#             pivot_value_str = working_tableau[pivot_row_index][pivot_index]
#             pivot_value = parse_fraction_string(pivot_value_str)
            
#             if pivot_value == 0:
#                 return render_template(
#                     "main.html",
#                     objective=objective,
#                     constraint1=constraint1,
#                     constraint2=constraint2,
#                     nonneg=nonneg,
#                     standard_form=standard_form,  # Pass standard_form
#                     tableau1=tableau1,
#                     tableau_highlight=tableau_highlight,
#                     pivot_index=pivot_index,
#                     tableau_ratio=tableau_ratio,
#                     pivot_row_index=pivot_row_index,
#                     solution_error="Pivot element is zero (cannot divide)."
#                 )

#             # SOLUTIONS
#             column_names = ["B.V", "x", "y", "S₁", "S₂", "RHS"]
#             pivot_col_name = column_names[pivot_index] if pivot_index < len(column_names) else f"Col{pivot_index}"
            
#             # Calculate reciprocal for display
#             reciprocal_display = ""
#             if pivot_value != 0:
#                 reciprocal = 1 / pivot_value
#                 reciprocal_display = format_number(reciprocal)
            
#             # Use Markup to allow HTML in solution headers - FIXED to show reciprocal
#             if reciprocal_display:
#                 solution1_header = Markup(f"{working_tableau[pivot_row_index][0]}({reciprocal_display})→{pivot_col_name}")
#             else:
#                 solution1_header = Markup(f"{working_tableau[pivot_row_index][0]}(1/k)→{pivot_col_name}")
            
#             solution1 = []
#             solution1_results = []
            
#             for j in range(1, len(working_tableau[0])):
#                 old_val_str = working_tableau[pivot_row_index][j]
#                 old_val = parse_fraction_string(old_val_str)
#                 result = old_val / pivot_value
                
#                 # FIXED: Show the actual reciprocal, not "1/k"
#                 if reciprocal_display:
#                     solution1.append(f"{format_number(old_val)}({reciprocal_display}) = {format_number(result)}")
#                 else:
#                     solution1.append(f"{format_number(old_val)}(1/{format_number(pivot_value)}) = {format_number(result)}")
                
#                 solution1_results.append(result)
            
#             other_row = 1 - pivot_row_index
#             P_other_str = working_tableau[other_row][pivot_index]
#             P_other = parse_fraction_string(P_other_str)
            
#             solution2_header = Markup(f"{working_tableau[other_row][0]} = {working_tableau[other_row][0]} - {pivot_col_name}(P {working_tableau[other_row][0]})")
#             solution2 = []
            
#             for j in range(1, len(working_tableau[0])):
#                 old_val_str = working_tableau[other_row][j]
#                 old_val = parse_fraction_string(old_val_str)
#                 pivot_row_result = solution1_results[j-1]
#                 new_val = old_val - pivot_row_result * P_other
#                 calc_str = f"{format_number(old_val)} - {format_number(pivot_row_result)}({format_number(P_other)}) = {format_number(new_val)}"
#                 solution2.append(calc_str)
            
#             P_z_str = working_tableau[2][pivot_index]
#             P_z = parse_fraction_string(P_z_str)
            
#             solution3_header = Markup(f"z = z - {pivot_col_name}(P z)")
#             solution3 = []
            
#             for j in range(1, len(working_tableau[0])):
#                 old_val_str = working_tableau[2][j]
#                 old_val = parse_fraction_string(old_val_str)
#                 pivot_row_result = solution1_results[j-1]
#                 new_val = old_val - pivot_row_result * P_z
#                 calc_str = f"{format_number(old_val)} - {format_number(pivot_row_result)}({format_number(P_z)}) = {format_number(new_val)}"
#                 solution3.append(calc_str)

#             new_tableau = perform_pivot_operations(working_tableau, pivot_row_index, pivot_index)
#             has_negative_in_z = check_negative_in_z_row(new_tableau)

#             # Determine next iteration count
#             if is_iteration:
#                 tableau2 = new_tableau
#                 next_iteration = iteration_count + 1
#             else:
#                 tableau2 = new_tableau
#                 next_iteration = 2

#             return render_template(
#                 "main.html",
#                 objective=objective,
#                 constraint1=constraint1,
#                 constraint2=constraint2,
#                 nonneg=nonneg,
#                 standard_form=standard_form,  # Pass standard_form
#                 tableau1=tableau1,
#                 tableau_highlight=tableau_highlight,
#                 tableau2_highlight=tableau2_highlight,
#                 pivot_index=pivot_index,
#                 tableau_ratio=tableau_ratio,
#                 tableau2_ratio=tableau2_ratio,
#                 pivot_row_index=pivot_row_index,
#                 solution1_header=solution1_header,
#                 solution1=solution1,
#                 solution2_header=solution2_header,
#                 solution2=solution2,
#                 solution3_header=solution3_header,
#                 solution3=solution3,
#                 tableau2=tableau2,
#                 has_negative_in_z=has_negative_in_z,
#                 show_solution_button=True,
#                 current_tableau_data=json.dumps([[str(cell) for cell in row] for row in new_tableau]) if new_tableau else None,
#                 iteration_count=iteration_count,
#                 next_iteration=next_iteration
#             )

#     # Render template with all variables (for backward compatibility)
#     return render_template(
#         "main.html",
#         objective=objective,
#         constraint1=constraint1,
#         constraint2=constraint2,
#         nonneg=nonneg,
#         standard_form=standard_form,
#         tableau1=tableau1,
#         tableau_highlight=tableau_highlight,
#         tableau2_highlight=tableau2_highlight,
#         pivot_index=pivot_index,
#         tableau_ratio=tableau_ratio,   
#         tableau2_ratio=tableau2_ratio,
#         pivot_row_index=pivot_row_index,
#         solution1_header=solution1_header,
#         solution1=solution1,
#         solution2_header=solution2_header,
#         solution2=solution2,
#         solution3_header=solution3_header,
#         solution3=solution3,
#         show_solution_button=show_solution_button,
#         show_pivotrow_button=show_pivotrow_button,
#         tableau2=tableau2,
#         has_negative_in_z=has_negative_in_z,
#         current_tableau_data=current_tableau_data,
#         iteration_count=iteration_count,      
#         next_iteration=next_iteration,
#         all_steps=all_steps,
#         display_all_steps=display_all_steps
#     )

# # ==================== ADDED ABOUT ROUTE ====================
# @app.route("/about")
# def about_page():
#     return render_template("about.html")
# # ===========================================================

# if __name__ == "__main__":
#     app.run(debug=True)