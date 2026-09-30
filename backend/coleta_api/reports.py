"""Exportações filtradas e resumo operacional da transportadora."""
import csv
from datetime import date,datetime
from io import BytesIO,StringIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo
from uuid import UUID
from fastapi import Depends,HTTPException
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from .collections import SELECT_COLLECTION,Status,Origin,QuantityStatus,history_filter


def report_filters(cliente_id:UUID|None=None,motorista_id:UUID|None=None,modalidade_id:UUID|None=None,
                   data_inicio:date|None=None,data_fim:date|None=None,status:Status|None=None,
                   origem:Origin|None=None,quantidade_status:QuantityStatus|None=None):
    return dict(cliente_id=cliente_id,motorista_id=motorista_id,modalidade_id=modalidade_id,
                data_inicio=data_inicio,data_fim=data_fim,status=status,origem=origem,
                quantidade_status=quantidade_status)


def safe_csv(value):
    text='' if value is None else str(value)
    if text.lstrip().startswith(('=','+','-','@','\t','\r','\n')):
        return "'"+text
    return text


def report_rows(conn,user,filters,max_rows,max_items):
    zone,clause,params,item_where,item_params=history_filter(conn,user,**filters)
    count=conn.execute('SELECT count(*) AS total FROM coletas c'+clause,params).fetchone()['total']
    if count>max_rows:
        raise HTTPException(422,f'O filtro contém mais de {max_rows} coletas. Reduza o período para exportar.')
    rows=conn.execute(SELECT_COLLECTION+clause+' ORDER BY data_referencia DESC,c.id',params).fetchall()
    ids=[row['id'] for row in rows]
    where=' AND '+' AND '.join(item_where) if item_where else ''
    item_count=conn.execute('''SELECT count(*) AS total FROM coleta_itens i
        WHERE i.coleta_id=ANY(%s)'''+where,[ids,*item_params]).fetchone()['total']
    if item_count>max_items:
        raise HTTPException(422,f'O filtro contém mais de {max_items} itens de coleta. Reduza o período para exportar.')
    items=conn.execute('''SELECT i.coleta_id,i.modalidade_nome,i.quantidade,i.quantidade_status
        FROM coleta_itens i WHERE i.coleta_id=ANY(%s)'''+where+' ORDER BY i.modalidade_nome,i.id',
        [ids,*item_params]).fetchall()
    by_id={cid:[] for cid in ids}
    for item in items:
        by_id[item['coleta_id']].append(item)
    for row in rows:
        row['itens']=by_id[row['id']]
    return zone,rows


def summary(rows):
    return {'total':len(rows),'agendadas':sum(r['status']=='agendada' for r in rows),
            'concluidas':sum(r['status']=='concluida' for r in rows),
            'nao_atendidas':sum(r['status']=='nao_atendida' for r in rows),
            'canceladas':sum(r['status']=='cancelada' for r in rows),
            'itens_a_conferir':sum(i['quantidade_status']=='a_conferir' for r in rows if r['status']=='concluida' for i in r['itens']),
            'volumes_confirmados':sum(i['quantidade'] or 0 for r in rows if r['status']=='concluida' for i in r['itens'] if i['quantidade_status']=='confirmada')}


def local_stamp(value,zone):
    return value.astimezone(ZoneInfo(zone)).strftime('%d/%m/%Y %H:%M')


def pdf_report(company,zone,rows,filters):
    output=BytesIO()
    doc=SimpleDocTemplate(output,pagesize=landscape(A4),rightMargin=34,leftMargin=34,topMargin=36,bottomMargin=36)
    styles=getSampleStyleSheet()
    title=ParagraphStyle('ColetaTitle',parent=styles['Title'],fontName='Helvetica-Bold',fontSize=18,leading=22,textColor=colors.HexColor('#152d3b'),spaceAfter=6)
    small=ParagraphStyle('ColetaSmall',parent=styles['Normal'],fontSize=8,leading=12,textColor=colors.HexColor('#516674'))
    cell=ParagraphStyle('ColetaCell',parent=styles['Normal'],fontSize=8,leading=11,wordWrap='CJK')
    head=ParagraphStyle('ColetaHead',parent=cell,fontName='Helvetica-Bold',textColor=colors.white)
    s=summary(rows)
    period=f"{filters['data_inicio'].strftime('%d/%m/%Y') if filters['data_inicio'] else 'Início'} a {filters['data_fim'].strftime('%d/%m/%Y') if filters['data_fim'] else 'Hoje'}"
    count_label=lambda count,singular,plural:f'{count} {singular if count==1 else plural}'
    story=[Paragraph('Histórico de coletas',title),Paragraph(escape(company)+'  |  Período: '+escape(period)+'  |  Fuso: '+escape(zone),small),Spacer(1,12),
           Paragraph('  •  '.join([count_label(s['total'],'registro','registros'),count_label(s['concluidas'],'concluída','concluídas'),
                count_label(s['agendadas'],'agendada','agendadas'),count_label(s['nao_atendidas'],'não atendida','não atendidas'),
                count_label(s['itens_a_conferir'],'item a conferir','itens a conferir'),count_label(s['volumes_confirmados'],'volume confirmado','volumes confirmados')]),small),Spacer(1,16)]
    table_data=[[Paragraph(x,head) for x in ('Data','Cliente','Motorista','Situação','Origem','Modalidades e volumes')]]
    names={'agendada':'Agendada','concluida':'Concluída','nao_atendida':'Não atendida','cancelada':'Cancelada'}
    for row in rows:
        base=[local_stamp(row['data_referencia'],zone),row['cliente_nome'],row['motorista_nome'],
              names.get(row['status'],row['status']),'Rota fixa' if row['origem']=='rota_fixa' else 'Chamado imprevisto']
        for item in row['itens'] or [None]:
            details=(f"{item['modalidade_nome']}: {item['quantidade'] if item['quantidade'] is not None else 'não informada'}"+
                     (' (a conferir)' if item['quantidade_status']=='a_conferir' else '')) if item else 'Sem itens'
            values=[*base,details]
            table_data.append([Paragraph(escape(str(v)),cell) for v in values])
    table=Table(table_data,colWidths=[87,172,120,90,93,211],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#152d3b')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f6f8')]),
        ('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#152d3b')),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    if rows:
        story.append(table)
    else:
        story.append(Paragraph('Nenhuma coleta encontrada para os filtros selecionados.',small))
    def footer(canvas,document):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#6b7f89'))
        canvas.drawString(34,20,'Coleta - relatório operacional')
        canvas.drawRightString(landscape(A4)[0]-34,20,f'Página {document.page}')
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()


def register_reports(app,staff):
    @app.get('/operacao/indicadores',tags=['Relatórios'])
    def indicators(auth=Depends(staff)):
        conn,user,_=auth
        zone=conn.execute('SELECT fuso_horario FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()['fuso_horario']
        today=datetime.now(ZoneInfo(zone)).date()
        # A situação diária usa o mesmo fuso da transportadora e a referência do histórico.
        start=datetime.combine(today,datetime.min.time(),ZoneInfo(zone))
        from datetime import timedelta
        end=start+timedelta(days=1)
        counts=conn.execute('''SELECT count(*) AS total,
            count(*) FILTER(WHERE status='agendada') AS agendadas,
            count(*) FILTER(WHERE status='concluida') AS concluidas,
            count(*) FILTER(WHERE status='nao_atendida') AS nao_atendidas,
            count(*) FILTER(WHERE status='cancelada') AS canceladas,
            count(*) FILTER(WHERE origem='chamado_imprevisto') AS chamados
            FROM coletas WHERE coalesce(concluida_em,agendada_para,criado_em)>=%s
              AND coalesce(concluida_em,agendada_para,criado_em)<%s''',(start,end)).fetchone()
        pending=conn.execute('''SELECT count(*) AS itens_a_conferir FROM coleta_itens i
            JOIN coletas c ON c.id=i.coleta_id AND c.empresa_id=i.empresa_id
            WHERE c.status='concluida' AND i.quantidade_status='a_conferir' ''').fetchone()['itens_a_conferir']
        return {'data':today,'fuso_horario':zone,**counts,'itens_a_conferir':pending}

    @app.get('/coletas/exportar.csv',tags=['Relatórios'])
    def export_csv(filters=Depends(report_filters),auth=Depends(staff)):
        conn,user,_=auth
        zone,rows=report_rows(conn,user,filters,10000,50000)
        stream=StringIO(newline='')
        writer=csv.writer(stream,delimiter=';')
        writer.writerow(['Data local','Cliente','CNPJ','Motorista','Situação','Origem','Modalidades e volumes','Volumes confirmados','Itens a conferir','Observações'])
        for row in rows:
            details=' | '.join(f"{i['modalidade_nome']}: {i['quantidade'] if i['quantidade'] is not None else 'não informada'}"+
                (' (a conferir)' if i['quantidade_status']=='a_conferir' else '') for i in row['itens'])
            totals=summary([row])
            writer.writerow([safe_csv(value) for value in [local_stamp(row['data_referencia'],zone),row['cliente_nome'],
                row['cliente_cnpj'],row['motorista_nome'],row['status'],row['origem'],details,
                totals['volumes_confirmados'],totals['itens_a_conferir'],row['observacoes']]])
        totals=summary(rows)
        writer.writerow([f"TOTAL ({totals['total']} {'coleta' if totals['total']==1 else 'coletas'})",'','','','','','',
            totals['volumes_confirmados'],totals['itens_a_conferir'],''])
        return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',
            headers={'Content-Disposition':f'attachment; filename="coletas-{date.today():%Y%m%d}.csv"','Cache-Control':'no-store'})

    @app.get('/coletas/exportar.pdf',tags=['Relatórios'])
    def export_pdf(filters=Depends(report_filters),auth=Depends(staff)):
        conn,user,_=auth
        zone,rows=report_rows(conn,user,filters,1000,5000)
        company=conn.execute('SELECT nome FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()['nome']
        content=pdf_report(company,zone,rows,filters)
        return Response(content,media_type='application/pdf',headers={
            'Content-Disposition':f'attachment; filename="coletas-{date.today():%Y%m%d}.pdf"','Cache-Control':'no-store'})
