#!/usr/bin/env python3
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable, PageBreak)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

C_RED     = colors.HexColor('#E2231A')
C_NAVY    = colors.HexColor('#1F3864')
C_BLUE    = colors.HexColor('#4472C4')
C_BLITE   = colors.HexColor('#EBF3FF')
C_BHDR    = colors.HexColor('#E8F0FB')
C_BGRAY   = colors.HexColor('#F5F5F5')
C_MGRAY   = colors.HexColor('#CCCCCC')
C_DARK    = colors.HexColor('#1A1A1A')
C_GRAY    = colors.HexColor('#777777')
C_WHITE   = colors.white

PAGE_W, PAGE_H = A4
M  = 15 * mm
UW = PAGE_W - 2 * M   # ~180mm

def PS(name, **kw):
    d = dict(fontName='Helvetica', fontSize=8, textColor=C_DARK, leading=11)
    d.update(kw)
    return ParagraphStyle(name, **d)

sN   = PS('n')
sB   = PS('b', fontName='Helvetica-Bold')
sSm  = PS('sm', fontSize=7, textColor=C_GRAY, leading=10)
sH1  = PS('h1', fontName='Helvetica-Bold', fontSize=10, textColor=C_NAVY, spaceBefore=5, spaceAfter=3)
sH2  = PS('h2', fontName='Helvetica-Bold', fontSize=7.5, textColor=C_BLUE)
sW   = PS('w', fontName='Helvetica-Bold', textColor=C_WHITE)
sR   = PS('r', alignment=TA_RIGHT)
sC   = PS('c', alignment=TA_CENTER)
sRed = PS('red', fontName='Helvetica-Bold', fontSize=18, textColor=C_RED)
sBl7 = PS('bl7', fontName='Helvetica-Bold', fontSize=7, textColor=C_BLUE)

def tbl_style_inner():
    return TableStyle([
        ('TOPPADDING',    (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('LEFTPADDING',   (0,0),(-1,-1), 6),
        ('RIGHTPADDING',  (0,0),(-1,-1), 6),
        ('BACKGROUND',    (0,0),(-1,0),  C_BHDR),
    ])

def build():
    out = '/Users/danny/VibeCoding/PriceGrid/Lenovo_Merged_Quote.pdf'
    doc = SimpleDocTemplate(out, pagesize=A4,
                            leftMargin=M, rightMargin=M,
                            topMargin=M, bottomMargin=M)
    story = []

    # ── PAGE 1 ────────────────────────────────────────────────

    # Header
    lh = Table([
        [Paragraph('Lenovo', sRed)],
        [Paragraph('LGFS · LENOVO GLOBAL FINANCIAL SERVICE', sBl7)],
    ], colWidths=[UW * 0.55])
    lh.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),1),
                             ('LEFTPADDING',(0,0),(-1,-1),0)]))

    rh = Table([
        [Paragraph('BRPASM000833172 / QT-20260313-6047',
                   PS('rid', fontName='Helvetica-Bold', fontSize=9, textColor=C_RED, alignment=TA_RIGHT))],
        [Paragraph('Quotation Proposal',
                   PS('qp', fontSize=8, alignment=TA_RIGHT))],
        [Paragraph('18 Mar 2026',
                   PS('qd', fontSize=7, textColor=C_GRAY, alignment=TA_RIGHT))],
    ], colWidths=[UW * 0.45])
    rh.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),1)]))

    hdr = Table([[lh, rh]], colWidths=[UW*0.55, UW*0.45])
    hdr.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width='100%', thickness=2, color=C_RED, spaceAfter=3*mm))

    # Info bar
    ibar = Table([[
        Paragraph('<b>Quote Date:</b>  18 Mar 2026', sN),
        Paragraph('<b>Valid Until:</b>  17 Apr 2026', sN),
        Paragraph('<b>Bid Ref:</b>  BRPASM000833172 V1', sN),
        Paragraph('<b>Quote Value:</b>  USD 6,992.04', sN),
    ]], colWidths=[UW/4]*4)
    ibar.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),C_BGRAY),
        ('BOX',(0,0),(-1,-1),0.5,C_MGRAY),
        ('LINEAFTER',(0,0),(2,0),0.5,C_MGRAY),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),7),
    ]))
    story.append(ibar)
    story.append(Spacer(1, 4*mm))

    # Prepared For / Prepared By
    h = UW/2
    pf = Table([
        [Paragraph('PREPARED FOR', sH2)],
        [Paragraph('<b>COCA-COLA SOUTH PACIFIC</b>', sN)],
        [Paragraph('Account Hierarchy: COKE_HQ', sN)],
        [Paragraph('Customer Number: 1212318929', sN)],
        [Paragraph('Asset Recovery Service: Not Included', sN)],
    ], colWidths=[h-2])
    pf.setStyle(tbl_style_inner())

    pb = Table([
        [Paragraph('PREPARED BY — LGFS CONTACT', sH2)],
        [Paragraph('Hongfei HF9 Zhu | <font name="STSong-Light">\u6731\u6cf3\u970a</font>', sB)],
        [Paragraph('Sales Representative', sN)],
        [Paragraph('Email: zhuhf9@lenovo.com', sN)],
        [Paragraph('Portal: lgfs.lenovo.com', sN)],
    ], colWidths=[h-2])
    pb.setStyle(tbl_style_inner())

    pfpb = Table([[pf, pb]], colWidths=[h, h])
    pfpb.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),0.5,C_MGRAY),
        ('LINEBEFORE',(1,0),(1,0),0.5,C_MGRAY),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
    ]))
    story.append(pfpb)
    story.append(Spacer(1, 4*mm))

    # 3-column: Lease / Currency / Deal
    c3 = UW/3
    ls = Table([
        [Paragraph('LEASE STRUCTURE', sH2)],
        [Paragraph('Term: <b>36 months</b>', sN)],
        [Paragraph('Frequency: <b>Monthly</b>', sN)],
        [Paragraph('Timing: <b>Arrears</b>', sN)],
        [Paragraph('Payment Terms: <b>30 days</b>', sN)],
    ], colWidths=[c3-2])
    ls.setStyle(tbl_style_inner())

    cp = Table([
        [Paragraph('CURRENCY &amp; PRICING', sH2)],
        [Paragraph('Multi-Currency (see details p.2)', sN)],
        [Paragraph('Guideline LRF: <b>2.6191%</b>', sN)],
        [Paragraph('Priced LRF: <b>2.5684%</b>', sN)],
        [Paragraph('Est. Payment: <b>EUR 25.68</b>', sN)],
    ], colWidths=[c3-2])
    cp.setStyle(tbl_style_inner())

    ds = Table([
        [Paragraph('DEAL SUMMARY', sH2)],
        [Paragraph('Total Asset Value: <b>USD 6,992.04</b>', sN)],
        [Paragraph('Residual Value: <b>19.00%</b>', sN)],
        [Paragraph('Sum of Payments: <b>92.4615%</b>', sN)],
        [Paragraph('Credit Grade: <b>5 \u2013 1.0% (Default)</b>', sN)],
    ], colWidths=[c3-2])
    ds.setStyle(tbl_style_inner())

    lcd = Table([[ls, cp, ds]], colWidths=[c3, c3, c3])
    lcd.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),0.5,C_MGRAY),
        ('LINEAFTER',(0,0),(1,0),0.5,C_MGRAY),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
    ]))
    story.append(lcd)
    story.append(Spacer(1, 5*mm))

    # BOM
    story.append(Paragraph('BILL OF MATERIALS (BOM)', sH1))
    bcw = [8*mm, 26*mm, 80*mm, 22*mm, 15*mm, 10*mm]
    brows = [
        [Paragraph('#',sW), Paragraph('Part Number',sW), Paragraph('Description',sW),
         Paragraph('Category',sW), Paragraph('OEM',sW),
         Paragraph('Qty', PS('bqh', fontName='Helvetica-Bold', textColor=C_WHITE, alignment=TA_CENTER))],
        ['1','11T3009VAU','Desktop TC M70q Gen 3 I512400T 16G N W11','Desktop/TC','Lenovo','5'],
        ['2','5WS0U26647','WARRANTY 3Y Premier Support','Warranty','Lenovo','5'],
        ['3','4XH0N04098','ACCKIT_BO Tiny Sandwich Kit II','Accessory','Lenovo','5'],
        ['4','11TN0029US','Desktop TC M90t Gen 3 I712700 16G N W11P','Desktop/TC','Lenovo','5'],
        ['5','4XE0N80914','SECUR_BO KST MS DS2.0 Cable Lock','Security','Lenovo','5'],
        ['6','11U5002QUS','Desktop TC M90q Gen 3 I712700T 16G N W11','Desktop/TC','Lenovo','5'],
        ['7','11T4S0YB00','Desktop TC M70q Gen 3 I512400T 8G N W11D','Desktop/TC','Lenovo','5'],
        ['','','','',
         Paragraph('Total Asset Lines:', PS('tal', fontName='Helvetica-Bold', textColor=C_BLUE, alignment=TA_RIGHT, fontSize=7.5)),
         Paragraph('7 units', PS('tu', fontName='Helvetica-Bold', textColor=C_BLUE, alignment=TA_CENTER, fontSize=7.5))],
    ]
    bt = Table(brows, colWidths=bcw, repeatRows=1)
    bts = TableStyle([
        ('BACKGROUND',(0,0),(-1,0),C_BLUE),
        ('FONTSIZE',(0,0),(-1,-1),7.5),
        ('ALIGN',(0,0),(0,-1),'CENTER'),
        ('ALIGN',(5,0),(5,-1),'CENTER'),
        ('GRID',(0,0),(-1,-2),0.3,C_MGRAY),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BACKGROUND',(0,-1),(-1,-1),C_BLITE),
        ('LINEABOVE',(0,-1),(-1,-1),0.5,C_NAVY),
    ])
    for i in range(2, 9, 2):
        bts.add('BACKGROUND',(0,i),(-1,i),C_BLITE)
    bt.setStyle(bts)
    story.append(bt)
    story.append(Paragraph('* CapEx pricing omitted. Contact your LGFS representative for asset cost details.', sSm))

    # ── PAGE 2 ────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph('LOCAL COUNTRY PRODUCT AND SERVICES DETAILS', sH1))
    story.append(Paragraph(
        'All prices are monthly installments | 36-month recurring term | Qty: 5 units per line item',
        sSm))
    story.append(Spacer(1, 3*mm))

    COUNTRIES = [
        ('Australia','AUD',[
            ('11T3009VAU','Desktop TC M70q Gen 3 I512400T 16G N W11','27.27','30.00'),
            ('5WS0U26647','WARRANTY 3Y Premier Support','6.85','7.54'),
            ('4XH0N04098','ACCKIT_BO Tiny Sandwich Kit II','2.98','3.28'),
            ('11TN0029US','Desktop TC M90t Gen 3 I712700 16G N W11P','86.17','94.78'),
            ('4XE0N80914','SECUR_BO KST MS DS2.0 Cable Lock','3.04','3.34'),
            ('11U5002QUS','Desktop TC M90q Gen 3 I712700T 16G N W11','71.23','78.35'),
            ('11T4S0YB00','Desktop TC M70q Gen 3 I512400T 8G N W11D','40.69','44.76'),
        ],'238.23','262.05'),
        ('Canada','CAD',[
            ('11T3009VAU','Desktop TC M70q Gen 3 I512400T 16G N W11','25.21','25.21'),
            ('5WS0U26647','WARRANTY 3Y Premier Support','6.41','6.41'),
            ('4XH0N04098','ACCKIT_BO Tiny Sandwich Kit II','2.78','2.78'),
            ('11TN0029US','Desktop TC M90t Gen 3 I712700 16G N W11P','79.95','79.95'),
            ('4XE0N80914','SECUR_BO KST MS DS2.0 Cable Lock','2.84','2.84'),
            ('11U5002QUS','Desktop TC M90q Gen 3 I712700T 16G N W11','66.07','66.07'),
            ('11T4S0YB00','Desktop TC M70q Gen 3 I512400T 8G N W11D','37.70','37.70'),
        ],'220.95','220.95'),
        ('India Onshore','INR',[
            ('11T3009VAU','Desktop TC M70q Gen 3 I512400T 16G N W11','2,081.45','2,081.45'),
            ('5WS0U26647','WARRANTY 3Y Premier Support','477.85','477.85'),
            ('4XH0N04098','ACCKIT_BO Tiny Sandwich Kit II','246.05','246.05'),
            ('11TN0029US','Desktop TC M90t Gen 3 I712700 16G N W11P','6,471.40','6,471.40'),
            ('4XE0N80914','SECUR_BO KST MS DS2.0 Cable Lock','250.80','250.80'),
            ('11U5002QUS','Desktop TC M90q Gen 3 I712700T 16G N W11','5,358.00','5,358.00'),
            ('11T4S0YB00','Desktop TC M70q Gen 3 I512400T 8G N W11D','3,082.75','3,082.75'),
        ],'17,968.30','17,968.30'),
        ('Japan','JPY',[
            ('11T3009VAU','Desktop TC M70q Gen 3 I512400T 16G N W11','3,127','3,127'),
            ('5WS0U26647','WARRANTY 3Y Premier Support','1,075','1,075'),
            ('4XH0N04098','ACCKIT_BO Tiny Sandwich Kit II','317','317'),
            ('11TN0029US','Desktop TC M90t Gen 3 I712700 16G N W11P','9,696','9,696'),
            ('4XE0N80914','SECUR_BO KST MS DS2.0 Cable Lock','323','323'),
            ('11U5002QUS','Desktop TC M90q Gen 3 I712700T 16G N W11','8,029','8,029'),
            ('11T4S0YB00','Desktop TC M70q Gen 3 I512400T 8G N W11D','5,057','5,057'),
        ],'27,626','27,626'),
        ('United States of America','USD',[
            ('11T3009VAU','Desktop TC M70q Gen 3 I512400T 16G N W11','18.67','18.67'),
            ('5WS0U26647','WARRANTY 3Y Premier Support','5.45','5.45'),
            ('4XH0N04098','ACCKIT_BO Tiny Sandwich Kit II','2.04','2.04'),
            ('11TN0029US','Desktop TC M90t Gen 3 I712700 16G N W11P','59.11','59.11'),
            ('4XE0N80914','SECUR_BO KST MS DS2.0 Cable Lock','2.52','2.52'),
            ('11U5002QUS','Desktop TC M90q Gen 3 I712700T 16G N W11','54.29','54.29'),
            ('11T4S0YB00','Desktop TC M70q Gen 3 I512400T 8G N W11D','27.89','27.89'),
        ],'169.97','169.97'),
    ]

    ccw = [8*mm, 25*mm, 73*mm, 10*mm, 18*mm, 11*mm, 17*mm, 18*mm]

    for cname, cur, items, tex, tinc in COUNTRIES:
        ch = Table([[
            Paragraph(f'Country:  <b>{cname}</b>',
                      PS('ch', textColor=C_WHITE, fontName='Helvetica-Bold', fontSize=8)),
            Paragraph(f'Currency:  <b>{cur}</b>',
                      PS('cr', textColor=C_WHITE, fontName='Helvetica-Bold', fontSize=8, alignment=TA_RIGHT)),
        ]], colWidths=[UW*0.6, UW*0.4])
        ch.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),C_NAVY),
            ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
            ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ]))
        story.append(ch)

        crow = [[
            Paragraph('#',sW), Paragraph('Part No.',sW), Paragraph('Description',sW),
            Paragraph('Qty', PS('cqh', fontName='Helvetica-Bold', textColor=C_WHITE, alignment=TA_CENTER)),
            Paragraph('Billing',sW),
            Paragraph('Term', PS('cth', fontName='Helvetica-Bold', textColor=C_WHITE, alignment=TA_CENTER)),
            Paragraph(f'Price\n({cur})', PS(f'prc{cur}', fontName='Helvetica-Bold', textColor=C_WHITE,
                                             alignment=TA_RIGHT, fontSize=7, leading=9)),
            Paragraph(f'Incl.Tax\n({cur})', PS(f'itx{cur}', fontName='Helvetica-Bold', textColor=C_WHITE,
                                                alignment=TA_RIGHT, fontSize=7, leading=9)),
        ]]
        for i,(pn,desc,price,incl) in enumerate(items):
            crow.append([
                str(i+1), pn, desc, '5', 'Monthly', '36',
                Paragraph(price, PS(f'pv{cur}{i}', alignment=TA_RIGHT, fontSize=7.5)),
                Paragraph(incl,  PS(f'iv{cur}{i}', alignment=TA_RIGHT, fontSize=7.5)),
            ])
        crow.append([
            '','','','','',
            Paragraph('Total', PS(f'tot{cur}', fontName='Helvetica-Bold', textColor=C_NAVY, alignment=TA_CENTER)),
            Paragraph(f'{cur} {tex}',  PS(f'tv{cur}', fontName='Helvetica-Bold', textColor=C_NAVY, alignment=TA_RIGHT, fontSize=7.5)),
            Paragraph(f'{cur} {tinc}', PS(f'ti{cur}', fontName='Helvetica-Bold', textColor=C_NAVY, alignment=TA_RIGHT, fontSize=7.5)),
        ])

        ct = Table(crow, colWidths=ccw, repeatRows=1)
        cts = TableStyle([
            ('BACKGROUND',(0,0),(-1,0),C_BLUE),
            ('FONTSIZE',(0,0),(-1,-1),7.5),
            ('ALIGN',(0,0),(0,-1),'CENTER'),
            ('ALIGN',(3,0),(5,-1),'CENTER'),
            ('GRID',(0,0),(-1,-2),0.3,C_MGRAY),
            ('TOPPADDING',(0,0),(-1,-1),2.5),('BOTTOMPADDING',(0,0),(-1,-1),2.5),
            ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('BACKGROUND',(0,-1),(-1,-1),C_BLITE),
            ('LINEABOVE',(0,-1),(-1,-1),1,C_NAVY),
            ('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ])
        for i in range(2, len(crow)-1, 2):
            cts.add('BACKGROUND',(0,i),(-1,i),C_BLITE)
        ct.setStyle(cts)
        story.append(ct)
        story.append(Spacer(1, 4*mm))

    # ── PAGE 3 ────────────────────────────────────────────────
    story.append(PageBreak())

    story.append(Paragraph('WHAT HAPPENS NEXT', sH1))
    steps = [
        "Return signed quote to your LGFS representative to initiate the credit application.",
        "Submit a formal Purchase Order (PO) referencing quote number <b>BRPASM000833172 / QT-20260313-6047</b>. PO should be addressed to LGFS (Lenovo Global Financial Service).",
        "Credit review is typically completed within 2\u20133 business days. Additional financial information may be requested.",
        "Upon credit approval, lease documentation is issued for execution. Commencement date and delivery schedule to be agreed.",
        "Assets delivered and lease commences. Access the LGFS portal (<b>lgfs.lenovo.com</b>) to manage assets, schedule returns, and view statements.",
    ]
    srows = [[
        Paragraph(str(i+1), PS(f'sn{i}', fontName='Helvetica-Bold', fontSize=9,
                               textColor=C_WHITE, alignment=TA_CENTER)),
        Paragraph(s, sN)
    ] for i,s in enumerate(steps)]

    st = Table(srows, colWidths=[10*mm, UW-10*mm])
    sts = TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
        ('LINEBELOW',(0,0),(-1,-2),0.3,C_MGRAY),
    ])
    for i in range(len(steps)):
        sts.add('BACKGROUND',(0,i),(0,i),C_BLUE)
        if i%2==1: sts.add('BACKGROUND',(1,i),(1,i),C_BGRAY)
    st.setStyle(sts)
    story.append(st)
    story.append(Spacer(1, 5*mm))

    story.append(Paragraph('ADDITIONAL SERVICES \u2014 ASK YOUR LGFS REPRESENTATIVE', sH1))
    scw = UW/4
    svcs = Table([[
        Paragraph('<b>Certified Data Wiping</b><br/>NIST 800-88 compliant end-of-lease data destruction with certificate of erasure', sN),
        Paragraph('<b>Logistics &amp; Deployment</b><br/>White-glove deployment, imaging, asset tagging and rollout management', sN),
        Paragraph('<b>Asset Recovery Service (ARS)</b><br/>Managed return, remarketing and recycling for owned assets', sN),
        Paragraph('<b>Fair Wear &amp; Tear</b><br/>End-of-lease fair wear &amp; tear coverage to protect against return condition charges', sN),
    ]], colWidths=[scw]*4)
    svcs.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),0.5,C_MGRAY),
        ('LINEAFTER',(0,0),(2,0),0.5,C_MGRAY),
        ('BACKGROUND',(0,0),(-1,-1),C_BLITE),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
    ]))
    story.append(svcs)
    story.append(Paragraph('Manage your assets, returns and invoices at lgfs.lenovo.com', sSm))
    story.append(Spacer(1, 5*mm))

    story.append(Paragraph('TERMS &amp; CONDITIONS', sH1))
    tcs = [
        "The sale and/or provision of goods and services by Lenovo is conditioned on Lenovo having signed the required agreement(s) with you. In the absence of any such agreements, Lenovo\u2019s then-current terms and conditions in the jurisdiction you are transacting shall govern.",
        "Acceptance by Lenovo of any purchase order is subject to your (i) having issued a purchase order referencing this quotation number for the full amount stated and (ii) your order having been confirmed in writing as accepted by Lenovo. This quotation is not capable of acceptance.",
        "Prices in this quotation are exclusive of value added taxes and any other tax or duty which (where applicable) must be added to the price payable.",
        "Prices are subject to Lenovo\u2019s final credit approval. Lenovo reserves the right to revise prices to account for increases in costs of materials, carriage, labor, taxes, duties, tariffs or exchange rate variations.",
        "This quote is provided by LGFS and is subject to: (i) satisfactory credit assessment and approval; (ii) execution of LGFS standard lease documentation; (iii) rate indexation \u2014 the lease rate factor is indicative based on swap rates at the rate basis date and will be confirmed at documentation; (iv) equipment availability; (v) applicable regulatory requirements. This quote does not constitute a commitment to lend or finance.",
        "This quotation supersedes all prior oral and written proposals and related communications in respect of the same subject matter.",
    ]
    for i,tc in enumerate(tcs):
        story.append(Paragraph(f'{i+1}.  {tc}', sSm))
        story.append(Spacer(1, 2*mm))

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph('ACCEPTANCE', sH1))

    dsc = Table([
        [Paragraph('<b>DocuSign</b>', PS('dsh', fontName='Helvetica-Bold', fontSize=11, textColor=C_BLUE))],
        [Paragraph('Sign electronically \u2014 fast, secure, legally binding', sSm)],
        [Spacer(1,2*mm)],
        [Paragraph('Your LGFS representative will send a DocuSign envelope to your registered email address.', sSm)],
        [Paragraph('Or scan the QR code sent with this quote to sign on mobile.', sSm)],
    ], colWidths=[UW*0.5-4])
    dsc.setStyle(TableStyle([
        ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
        ('LEFTPADDING',(0,0),(-1,-1),4),
    ]))

    mnl = Table([
        [Paragraph('\u2014 or sign manually below \u2014',
                   PS('mb', fontSize=7, textColor=C_GRAY, alignment=TA_CENTER))],
    ], colWidths=[UW*0.5-4])
    mnl.setStyle(TableStyle([
        ('VALIGN',(0,0),(0,0),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),
    ]))

    acc = Table([[dsc, mnl]], colWidths=[UW*0.5, UW*0.5])
    acc.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),0.5,C_MGRAY),
        ('LINEBEFORE',(1,0),(1,0),0.5,C_MGRAY),
        ('BACKGROUND',(0,0),(-1,-1),C_BGRAY),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
    ]))
    story.append(acc)
    story.append(Spacer(1, 5*mm))

    # Signature table
    sw = UW*0.46
    sp = UW*0.04
    sig = Table([
        [Paragraph('CUSTOMER AUTHORISED SIGNATORY', sB), '',
         Paragraph('LGFS AUTHORISED SIGNATORY', sB), ''],
        [Paragraph('Signature &amp; Date', sN), '', Paragraph('Signature &amp; Date', sN), ''],
        ['', '', '', ''],
        [Paragraph('Name &amp; Title', sN), '', Paragraph('Name &amp; Title', sN), ''],
        ['', '', '', ''],
        [Paragraph('Company', sN), '', Paragraph('LGFS \u2014 Lenovo Global Financial Service', sN), ''],
        ['', '', '', ''],
    ], colWidths=[sw, sp, sw, sp])
    sig.setStyle(TableStyle([
        ('FONTSIZE',(0,0),(-1,-1),7.5),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING',(0,0),(-1,-1),0),
        ('LINEBELOW',(0,2),(0,2),0.5,C_DARK),
        ('LINEBELOW',(2,2),(2,2),0.5,C_DARK),
        ('LINEBELOW',(0,4),(0,4),0.5,C_DARK),
        ('LINEBELOW',(2,4),(2,4),0.5,C_DARK),
        ('LINEBELOW',(0,6),(0,6),0.5,C_DARK),
        ('LINEBELOW',(2,6),(2,6),0.5,C_DARK),
    ]))
    story.append(sig)

    # Footer
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width='100%', thickness=1.5, color=C_RED))
    story.append(Spacer(1, 2*mm))
    ft = Table([[
        Paragraph('LGFS \u00b7 Lenovo Global Financial Service \u00b7 lgfs.lenovo.com', sSm),
        Paragraph('BRPASM000833172 / QT-20260313-6047    Confidential \u2014 For addressee only',
                  PS('fr', fontSize=7, textColor=C_GRAY, alignment=TA_RIGHT)),
    ]], colWidths=[UW*0.55, UW*0.45])
    ft.setStyle(TableStyle([
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
    ]))
    story.append(ft)
    story.append(Paragraph('<b>Thank you for choosing Lenovo!</b>',
                           PS('thx', fontName='Helvetica-Bold', fontSize=9,
                              textColor=C_RED, alignment=TA_CENTER, spaceBefore=4)))

    doc.build(story)
    print(f'Generated: {out}')

if __name__ == '__main__':
    build()
