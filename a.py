from flask import Flask, request, render_template, jsonify, redirect, url_for
import pandas as pd
import numpy as np
import os
import time
import uuid
import json

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

def convert_to_basic_types(data):
    """
    将所有非基本数据类型转换为基本数据类型
    """
    if isinstance(data, dict):
        return {k: convert_to_basic_types(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_basic_types(i) for i in data]
    elif isinstance(data, (pd.Timestamp, pd.Timedelta)):
        return str(data)
    elif isinstance(data, (pd.Series, pd.DataFrame)):
        return data.to_dict()
    elif isinstance(data, (np.int64, np.float64)):
        return data.item()
    else:
        return data

def process_file(file_path):
    df = pd.read_csv(file_path)
    
    bill_to_account_number = df['Bill to Account Number'].iloc[0]
    invoice_date = df['Invoice Date'].iloc[0]
    invoice_number = df['Invoice Number'].iloc[0]
    original_amount_due = df['Original Amount Due'].iloc[0]
    tracking_id_count = df['Express or Ground Tracking ID'].count()
    service_type_counts = df['Service Type'].value_counts().to_dict()
    
    shipment_date_counts = df['Shipment Date'].value_counts().to_dict()
    shipment_date_amounts = df.groupby('Shipment Date')['Net Charge Amount'].sum().to_dict()
    
    df['Tendered Date'] = pd.to_datetime(df['Tendered Date'], format='%Y%m%d')
    df['POD Delivery Date'] = pd.to_datetime(df['POD Delivery Date'], format='%Y%m%d')
    df['Transport Days'] = (df['POD Delivery Date'] - df['Tendered Date']).dt.days
    transport_days_counts = df['Transport Days'].value_counts().to_dict()

    recipient_state_counts = df['Recipient State'].value_counts().to_dict()
    zone_code_counts = df['Zone Code'].value_counts().to_dict()

    charge_columns = [col for col in df.columns if 'Tracking ID Charge Description' in col]
    charge_amount_columns = [col for col in df.columns if 'Tracking ID Charge Amount' in col]

    charge_summary = {}
    charge_counts = {}
    residential_count = 0
    transportation_charge_total = df['Transportation Charge Amount'].sum()

    for desc_col, amount_col in zip(charge_columns, charge_amount_columns):
        if desc_col in df.columns and amount_col in df.columns:
            charges = df[[desc_col, amount_col]].dropna()
            for _, row in charges.iterrows():
                description = row[desc_col]
                amount = row[amount_col]
                if description in charge_summary:
                    charge_summary[description] += amount
                    charge_counts[description] += 1
                else:
                    charge_summary[description] = amount
                    charge_counts[description] = 1
                if description == "Residential":
                    residential_count += 1

    charge_summary = {k: f"${v:.2f}" for k, v in charge_summary.items()}
    
    commercial_count = tracking_id_count - residential_count

    result = {
        'Bill to Account Number': bill_to_account_number,
        'Invoice Date': invoice_date,
        'Invoice Number': invoice_number,
        'Original Amount Due': original_amount_due,
        'Tracking ID Count': tracking_id_count,
        'Service Type Counts': service_type_counts,
        'Shipment Date Counts': shipment_date_counts,
        'Shipment Date Amounts': shipment_date_amounts,
        'Transport Days Counts': transport_days_counts,
        'Recipient State Counts': recipient_state_counts,
        'Zone Code Counts': zone_code_counts,
        'Charge Summary': charge_summary,
        'Charge Counts': charge_counts,
        'Transportation Charge Total': transportation_charge_total,
        'Residential Count': residential_count,
        'Commercial Count': commercial_count
    }

    # 将所有非基本数据类型转换为基本数据类型
    result = convert_to_basic_types(result)

    return result

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    start_time = time.time()
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.csv'):
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            
            result = process_file(file_path)
            processing_time = time.time() - start_time

            # 创建唯一链接并保存结果到文件
            shared_link = str(uuid.uuid4())
            result_file_path = os.path.join(RESULTS_FOLDER, f'{shared_link}.json')
            with open(result_file_path, 'w') as result_file:
                json.dump(result, result_file)

            return render_template('result.html', result=result, processing_time=processing_time, shared_link=shared_link)
    
    return render_template('index.html')

@app.route('/share/<shared_link>')
def share(shared_link):
    result_file_path = os.path.join(RESULTS_FOLDER, f'{shared_link}.json')
    if os.path.exists(result_file_path):
        with open(result_file_path, 'r') as result_file:
            result = json.load(result_file)
        return render_template('result.html', result=result, processing_time=None)
    else:
        return "Shared link not found", 404

if __name__ == '__main__':
    app.run(debug=True)
