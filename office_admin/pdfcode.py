import pdfkit
import base64
import os

path_to_wkhtmltopdf = r"D:\WKHTMLTOX\wkhtmltopdf\bin\wkhtmltopdf.exe"
config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)

output_path = "paystub_output.pdf"

# 🔥 Delete old file if it exists
if os.path.exists(output_path):
    os.remove(output_path)

# ✅ Full path to image
image_path = r"F:\INTERSNIP\HRMS\CODE\HRMS\venv\hrms\office_admin\aureus.png"

# ✅ Convert image to base64
with open(image_path, "rb") as img_file:
    b64_image = base64.b64encode(img_file.read()).decode("utf-8")

# Step 3: HTML content with local image path
html_string = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
 <style>
  body {{
    margin: 0;
    padding: 20px;
    font-family: Arial, sans-serif;
    font-size: 14px;
  }}

  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
    margin-bottom: -20px;
  }}

  .logo {{
    display: flex;
    align-items: flex-start;
  }}

  .logo img {{
    height: 80px;        /* Set fixed height */
    margin-top: 50px;
    padding: 0;
  }}

  .company-details {{
    text-align: right;
    line-height: 1.5;
    margin-top: -80px;
  }}

  .paystub-title {{
    background: #444;
    color: white;
    text-align: center;
    padding: 5px;
    font-weight: bold;
    margin: 20px 0 5px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    text-align: center;
  }}

  th, td{{
    border: 1px solid #ccc;
    padding: 6px;
  }}

  th {{
    background: #f4f4f4;
  }}

  .red {{
    color: red;
    font-weight: bold;
  }}

  .text-left {{
    text-align: left;
    padding-left: 8px;
  }}
</style>


</head>
<body>

<div class="header">
  <div class="logo">
    <img src="data:image/png;base64,{b64_image}" alt="Logo">
  </div>
  <div class="company-details">

    <strong>Aureus Infotech Inc.</strong><br>
    7250 Keele St. #381<br>
    Vaughan, ON, L4K 1Z8<br>
    <a href="mailto:info@aureusinfotech.com">info@aureusinfotech.com</a><br>
    www.aureusinfotech.com<br>
    Tel: +1-416-890-8380
  </div>
</div>

<div class="paystub-title">PAYSTUB</div>

<div>
  <strong>SAMIR PATEL</strong><br>
  2208 - 210 Streles Ave W, Brampton, ON - L6Y 2K3<br>
</div>

<table>
  <tr class="red">
    <th>EMPLOYEE ID</th>
    <th>PERIOD ENDING</th>
    <th>PAY DATE</th>
    <th>CHEQUE NUMBER</th>
  </tr>
  <tr>
    <td>E10016</td>
    <td>28-02-25</td>
    <td>15-03-25</td>
    <td>Direct Deposit</td>
  </tr>
</table>

<table>
  <tr>
    <th>INCOME</th><th>RATE</th><th>HOURS</th><th>CURRENT TOTAL</th>
    <th>DEDUCTIONS</th><th>CURRENT TOTAL</th><th>YTD</th>
  </tr>
  <tr>
    <td class="text-left">REGULAR</td><td></td><td></td><td>8333.33</td>
    <td class="text-left">CPP</td><td>528.06</td><td>1000.00</td>
  </tr>
  <tr>
    <td class="text-left">PROJECT BONUS</td><td></td><td></td><td>500.00</td>
    <td class="text-left">EI</td><td>150.33</td><td>300.00</td>
  </tr>
  <tr>
    <td class="text-left">LEADERSHIP BONUS</td><td></td><td></td><td>333.34</td>
    <td class="text-left">INCOME TAX</td><td>1989.44</td><td>4035.00</td>
  </tr>
</table>


<table>
  <tr>
    <th>YTD GROSS</th><th>YTD DEDUCTIONS</th><th>YTD NET PAY</th><th>CURRENT TOTAL</th><th>DEDUCTIONS</th><th>NET PAY</th>
  </tr>
  <tr>
    <td>18333.34</td><td>5335.66</td><td>12997.68</td><td>9166.67</td><td>2667.83</td><td>6498.84</td>
  </tr>
</table>

</body>
</html>
"""


import pdfkit

path_to_wkhtmltopdf = r"D:\WKHTMLTOX\wkhtmltopdf\bin\wkhtmltopdf.exe"
config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)

pdfkit.from_string(html_string, "paystub_output.pdf", configuration=config)
print("✅ PDF generated successfully")
