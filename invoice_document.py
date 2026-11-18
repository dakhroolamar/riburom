"""Invoice snapshots and decimal calculations shared by the editor and exports."""
import io
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from flask import abort

CENT = Decimal('0.01')
MAX_TOTAL = Decimal('9999999999.99')
FIELDS = {
    'supplier': 'Company address and contact details', 'supplier_gstin': 'Supplier GSTIN',
    'recipient': 'Billing address and contact details', 'recipient_gstin': 'Recipient GSTIN',
    'place': 'Place of supply and state code', 'payment': 'Payment instructions',
    'terms': 'Terms and conditions',
}
MODES = ('No GST', 'CGST + SGST', 'IGST')


def details_for(invoice, settings):
    if invoice and invoice.details:
        return invoice.details
    return dict(supplier='\n'.join(filter(None, [settings.footer_address, settings.footer_email, settings.footer_phone])),
                issued=(invoice.created_at.date() if invoice else date.today()).isoformat(),
                reverse='No', mode='No GST', taxes=[],
                lines=[dict(description=invoice.description if invoice else '', code='', qty='1',
                            rate=str(invoice.amount) if invoice else '', gst='0')])


def decimal_value(raw, maximum, positive=False):
    if not re.fullmatch(r'\d{1,10}(?:\.\d{1,2})?', raw):
        abort(400, description='Enter a number with up to two decimal places.')
    value = Decimal(raw)
    if value > maximum or (positive and value == 0):
        abort(400, description='Quantity, price or tax rate is outside the allowed range.')
    return raw


def clean(raw, limit):
    value = raw.strip()
    if len(value) > limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]', value):
        abort(400, description='Invoice text is too long or contains unsupported characters.')
    return value


def rows(form, keys, maximum):
    columns = [form.getlist(key) for key in keys]
    if len({len(column) for column in columns}) != 1 or len(columns[0]) > maximum:
        abort(400, description='Check the invoice rows.')
    return zip(*columns)


def parse_details(form):
    d = {key: clean(form.get(key, ''), 3000) for key in FIELDS}
    d.update(issued=form.get('issued', ''), mode=form.get('mode'), reverse=form.get('reverse'), lines=[], taxes=[])
    try:
        date.fromisoformat(d['issued'])
    except ValueError:
        abort(400, description='Enter the invoice issue date.')
    if d['mode'] not in MODES or d['reverse'] not in ('Yes', 'No'):
        abort(400, description='Select a valid GST treatment.')
    for desc, code, qty, rate, gst in rows(form, ('item', 'code', 'qty', 'rate', 'gst'), 100):
        desc = clean(desc, 10000)
        if not desc:
            abort(400, description='Each item needs a description.')
        d['lines'].append(dict(description=desc, code=clean(code, 20), qty=decimal_value(qty, MAX_TOTAL, True),
                               rate=decimal_value(rate, MAX_TOTAL), gst=decimal_value(gst, 100)))
    if not d['lines']:
        abort(400, description='Add at least one item.')
    for name, pct in rows(form, ('tax_name', 'tax_rate'), 20):
        name = clean(name, 80)
        if not name:
            abort(400, description='Name each additional tax.')
        d['taxes'].append(dict(name=name, pct=decimal_value(pct, 100)))
    return d


def totals(d):
    def rounded(n):
        return n.quantize(CENT, rounding=ROUND_HALF_UP)
    amounts, breakdown = [], {}
    for line in d['lines']:
        base = rounded(Decimal(line['qty']) * Decimal(line['rate']))
        amounts.append(base)
        rate = Decimal(line['gst'])
        components = {'CGST + SGST': ('CGST', 'SGST'), 'IGST': ('IGST',)}.get(d['mode'], ())
        for component in components:
            share = rate / len(components)
            key = f'{component} {share:f}%'
            breakdown[key] = breakdown.get(key, 0) + rounded(base * share / 100)
    subtotal = sum(amounts, Decimal(0))
    taxes = list(breakdown.items())
    for tax in d['taxes']:
        taxes.append((f"{tax['name']} {tax['pct']}%", rounded(subtotal * Decimal(tax['pct']) / 100)))
    reverse_gst = sum(breakdown.values()) if d['reverse'] == 'Yes' else Decimal(0)
    total = subtotal + sum(value for _, value in taxes) - reverse_gst
    if reverse_gst:
        taxes.append(('GST payable by recipient under reverse charge', -reverse_gst))
    if total > MAX_TOTAL:
        abort(400, description='Invoice total exceeds the supported amount.')
    return dict(amounts=amounts, subtotal=subtotal, taxes=taxes, total=total)


def word_file(invoice, d, amounts):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin = section.right_margin = Cm(1.8)
    section.header_distance, section.top_margin = Cm(.8), Cm(3.2)
    style = doc.styles['Normal']
    style.font.name, style.font.size = 'Calibri', Pt(11)
    title_style = doc.styles['Title']
    title_style.font.color.rgb = RGBColor.from_string('182820')
    title_props = title_style.element.get_or_add_pPr()
    border = title_props.find(qn('w:pBdr'))
    if border is not None:
        title_props.remove(border)
    heading = doc.styles['Heading 2'].font
    heading.color.rgb = RGBColor.from_string('254D40')
    brand = section.header.paragraphs[0]
    brand.add_run().add_picture(str(Path(__file__).parent / 'static/control-room/ri-burom-mark.png'), width=Cm(1.65))
    name = brand.add_run('   RI BUROM TOURS & TRAVELS')
    name.bold = True
    name.font.size = Pt(17)
    name.font.color.rgb = RGBColor.from_string('183E32')
    # Lock the letterhead content control while leaving the document body editable.
    wrapper, props, content = (OxmlElement(n) for n in ('w:sdt', 'w:sdtPr', 'w:sdtContent'))
    lock = OxmlElement('w:lock')
    lock.set(qn('w:val'), 'sdtContentLocked')
    brand._p.addprevious(wrapper)
    wrapper.extend([props, content])
    props.append(lock)
    content.append(brand._p)
    doc.add_paragraph(d.get('supplier', ''))
    if d.get('supplier_gstin'):
        doc.add_paragraph('Supplier GSTIN  ' + d['supplier_gstin'])
    doc.add_paragraph(f'Invoice RB-I-{invoice.id:05d}', 'Title')
    doc.add_paragraph(f"Issued  {d['issued']}     Due  {invoice.due_date}     Status  {invoice.status.title()}")
    doc.add_heading('Billed to', 2)
    doc.add_paragraph('\n'.join(filter(None, [invoice.customer, d.get('recipient')])))
    for key in ('recipient_gstin', 'place'):
        if d.get(key):
            doc.add_paragraph(FIELDS[key] + '  ' + d[key])
    doc.add_paragraph('Reverse charge  ' + d['reverse'])
    table = doc.add_table(rows=0, cols=5)
    table.style = 'Light Shading Accent 1'
    for col, width in zip(table.columns, (6.5, 1.6, 3.1, 2.1, 4.1)):
        col.width = Cm(width)
    def row(values):
        cells = table.add_row().cells
        for index, (cell, value) in enumerate(zip(cells, values)):
            cell.text = str(value)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_before = Pt(4)
            paragraph.paragraph_format.space_after = Pt(4)
            if index:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    row(('Description / SAC', 'Qty', 'Rate (₹)', 'GST %', 'Value (₹)'))
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
    for item, value in zip(d['lines'], amounts['amounts']):
        row(('\n'.join(filter(None, [item['description'], item['code']])), item['qty'], item['rate'],
             item['gst'] if d['mode'] != 'No GST' else '0', f'{value:,.2f}'))
    for label, value in [('Subtotal', amounts['subtotal']), *amounts['taxes'], ('Invoice total', amounts['total'])]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.add_run(f'{label}     ₹ {value:,.2f}').bold = label == 'Invoice total'
    for key in ('payment', 'terms'):
        if d.get(key):
            doc.add_heading(FIELDS[key], 2)
            doc.add_paragraph(d[key])
    signature = doc.add_paragraph('____________________________\nAuthorised signature and seal')
    signature.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    signature.paragraph_format.space_before = Pt(36)
    result = io.BytesIO()
    doc.save(result)
    result.seek(0)
    return result
