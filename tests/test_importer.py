from io import BytesIO
from zipfile import ZipFile
import pytest
from pydantic import ValidationError
from coleta_api.importer import preview,read_rows,MAX_BYTES
from coleta_api.models import Client, normalize_cnpj
from test_api import workbook, HEADERS, ROW


def test_numeric_and_alpha_cnpj():
    assert normalize_cnpj('00.958.251/0001-83')=='00958251000183'
    assert normalize_cnpj('12.ABC.345/01DE-35')=='12ABC34501DE35'
    for value in ['00000000000000','12ABC34501DE00','00958251000184','x']:
        with pytest.raises(ValueError):
            normalize_cnpj(value)


def test_contract_and_uf(customer):
    assert Client(**customer).contrato_status=='nao_informado'
    with pytest.raises(ValidationError):
        Client(**customer,contrato_status='com_contrato')
    with pytest.raises(ValidationError):
        Client(**{**customer,'estado':'XX'})


def test_xlsx_blank_columns_duplicate_and_formula():
    rows=preview(workbook([HEADERS,ROW,ROW]),'teste.xlsx')
    assert all(r['erros'] for r in rows)
    assert rows[0]['dados']['complemento']=='Quadra 1'
    formula=ROW.copy()
    formula[0]='=1+1'
    assert preview(workbook([HEADERS,formula]),'t.xlsx')[0]['erros']
    number=ROW.copy()
    number[-1]=958251000183
    assert any('texto' in e for e in preview(workbook([HEADERS,number]),'t.xlsx')[0]['erros'])


def test_bad_archive_and_headers():
    with pytest.raises(ValueError):
        preview(b'bad','t.xlsx')
    with pytest.raises(ValueError):
        preview(b'x'*(MAX_BYTES+1),'t.xlsx')
    with pytest.raises(ValueError):
        preview(workbook([['NOME'],['Cliente']]),'t.xlsx')
    with pytest.raises(ValueError):
        preview(workbook([HEADERS+['CNPJ'],ROW+['123']]),'t.xlsx')


def test_ods_repeated_empty_cells_and_rows():
    ns='xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
    def row(values):
        return '<table:table-row>'+''.join(f'<table:table-cell><text:p>{v}</text:p></table:table-cell>' for v in values)+'</table:table-row>'
    xml=f'<office:document-content {ns}><office:body><office:spreadsheet><table:table table:name="Clientes">'+row(HEADERS)+row(ROW)+'<table:table-row table:number-rows-repeated="100000"><table:table-cell table:number-columns-repeated="1000"/></table:table-row></table:table></office:spreadsheet></office:body></office:document-content>'
    data=BytesIO()
    with ZipFile(data,'w') as archive:
        archive.writestr('content.xml',xml)
    result=preview(data.getvalue(),'teste.ods')
    assert len(result)==1
    assert result[0]['erros']==[]
    assert result[0]['linha']==2
