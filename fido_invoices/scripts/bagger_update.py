import xmlrpclib
from datetime import datetime
from dateutil.relativedelta import *
from datetime import date
import csv,os
import logging
from xlrd import open_workbook
from random import randint

_logger = logging.getLogger(__name__)

# Insert Bagger records from source Yenagoa sales file
# Assumes that job title 'Bagger' exists in hr.job. If not YOU SHOULD create it.

# Command line ArgumentHandling
try:
    import argparse
    parser = argparse.ArgumentParser(description='Script for Updating baggers from xls file')
    parser.add_argument('-w', '--salesfile', help='e.g -w salesfile.csv', required=True)
    args = vars(parser.parse_args())
except ImportError:
    parser = None
if not os.path.exists('./data'):
    os.makedirs('./data')
if not os.path.exists('./OUT'):
    os.makedirs('./OUT')

WBFILE = args['salesfile']

#  Odoo Credentials
try:
    db = 'FPLDB10'
    username = 'admin'
    password = 'N0tAdmin'
    port = '8071'
    host = 'localhost'
    url = 'http://%s:%s' % (host, port)
    models = xmlrpclib.ServerProxy('%s/xmlrpc/2/object' % (url))
    common = xmlrpclib.ServerProxy('{}/xmlrpc/2/common'.format(url))
    uid = common.authenticate(db, username, password, {})

    assert uid,'com.login failed'
    version = common.version()
    # assert version['server_version'] == '10.0','Server not 10.0'
    print 'Logged in to Odoo Version: ',version
except Exception, e:

    raise



# Function to Create csv files from sheets in Sales Workbook
def csvextract():
    wb = open_workbook(WBFILE)

    print ('SHEETS IN SALES FILE')

    for i in range(0, wb.nsheets-1):
        sheet = wb.sheet_by_index(i)
        # print (sheet.name)

        path =  DATAFOLDER + '/%s.csv'
        with open( path %(sheet.name.replace(" ", "") + '-'+ TODAY), "w") as file:
            writer = csv.writer(file, delimiter=",")

            header = [cell.value for cell in sheet.row(0)]
            writer.writerow(header)

            for row_idx in range(1, sheet.nrows):
                row = [int(cell.value) if isinstance(cell.value, float) else cell.value
                       for cell in sheet.row(row_idx)]
                writer.writerow(row)

def get_bagger(baggername):
    # creates a bagger if not exist in hr.employee and/or return bagger_id
    # Also creates its contract if need be
    try:
        jobid_obj = models.execute_kw(db, uid, password, 'hr.job', 'search_read', \
                                  [[['name', '=', 'Bagger']]], {'fields': ['id']})

        if not jobid_obj:
            job_id = models.execute_kw(db, uid, password, 'hr.job', 'create',\
                                          [{'name': 'Bagger'}])
        else:
            job_id = jobid_obj[0]['id']

        assert job_id,'Job id not set'
        bagger_hr_obj = models.execute_kw(db, uid, password, 'hr.employee', 'search_read', \
                         [[['name', '=', baggername]]], {'fields': ['id','name']})

        if not bagger_hr_obj:
            # Create Bagger in hr.employee
            employee_id = models.execute_kw(db, uid, password, 'hr.employee', 'create',\
                                          [{'name': baggername,'job_id': job_id}])
            assert employee_id,'Bagger Creation Fails'
            print 'Bagger Employee Created for: '+ baggername
        else:
            employee_id = bagger_hr_obj[0]['id']
            print 'Using existing Bagger Employee : ' + bagger_hr_obj[0]['name']

        # Create contract in hr.contract if not exist
        hr_contract_obj = models.execute_kw(db, uid, password, 'hr.contract', 'search_read', \
                            [[['employee_id', '=', employee_id]]], {'fields': ['id']})
        if not hr_contract_obj:

            contract_ref = baggername + '-Contract'
            type_id = models.execute_kw(db, uid, password, 'hr.contract.type', 'search_read', \
                            [[['name', '=', 'Employee']]], {'fields': ['id']})[0]['id']

            struct_obj = models.execute_kw(db, uid, password, 'hr.payroll.structure', 'search_read', \
                            [[['name', '=', 'Contract']]], {'fields': ['id']})

            if not struct_obj:
                struct_id = models.execute_kw(db, uid, password, 'hr.payroll.structure', 'create', \
                                  [{'name': 'Contract','code':'Contract'}])
            else:
                struct_id = struct_obj[0]['id']

            assert struct_id,'Payroll Structure Contract Not valid'
            date_start = date.today().strftime('%Y-%m-%d')
            wage = 0.0
            bagged_mult = 2.5
            kpbg_sold = 0.0
            obbg_sold = 0.0
            bagsold_mult = 1
            obbgsold_mult = 1
            kpbgsold_mult = 1
            cratesold_mult = 5
            crate_sold = 0.0
            disp_sold = 0.0
            dispsold_mult =25
            sal_adv = loan_adv = payee = days_absent = 0.0

            hr_contract = models.execute_kw(db, uid, password, 'hr.contract', 'create',\
                            [{'name': contract_ref,'employee_id':employee_id,'job_id':job_id,'type_id': type_id,'struct_id':struct_id,\
                            'date_start':date_start,'wage':wage,
                             'bagged_mult':bagged_mult,'kpbg_sold':kpbg_sold,'obbg_sold':obbg_sold,
                              'bagsold_mult': bagsold_mult,'obbgsold_mult':obbgsold_mult,'kpbgsold_mult':kpbgsold_mult,
                            'cratesold_mult':cratesold_mult,'crate_sold':crate_sold,'disp_sold':disp_sold,'dispsold_mult':dispsold_mult,
                              'sal_adv':sal_adv,'loan_adv':loan_adv, 'payee':payee,'days_absent':days_absent\
                              }])
            assert hr_contract,'hr_contract creation fails'
        else:
            hr_contract = hr_contract_obj[0]['id']
            assert hr_contract,'Contract not set for bagger'

        return employee_id
    except Exception, e:
        print 'get_bagger() Error: ' +  str(e)
        raise


# open the INVOICE worksheet and read its data into Odoo
TODAY = datetime.now().strftime('%d-%m-%Y')
DATAFOLDER = 'data'
SALESFILE = 'data/BAGGER-DAILY-'+ TODAY +'.csv'
OUTF = '/tmp/bagger_out.csv'
ERRF = '/tmp/bagger_err.csv'
outfile = open(OUTF,'w')
errfile = open(ERRF,'w')

# writes outputs and errors for review
head = 'SN,Name,QTY,MONTH,DATE,REMARK'
outfile.write(head+'\n')
errfile.write(head+'\n')
bagger_totals = 0
sn = esn = 0

# Extract csv from xls file
csvextract()

# Open Bagger File and Update Bagger Record
with open(SALESFILE, 'rb') as csvfile:
    line = csv.DictReader(csvfile)

    for row in line:
        try:
            dt = date.today()
            DAY = dt.day
            bagger_name = row['Name'].strip().upper()
            if not bagger_name:
                bagger_name = row['NAME'].strip().upper()

            qty = row['QTY'].strip()
            if not qty:
                qty = 0

            bmonth = row['MONTH'].strip().lower()
            bdate = datetime.strptime(row['DATE'].strip(), '%Y.%m.%d')
            if bdate.day <28:
                bmonth = str(bdate.strftime('%B')).lower()
            else:
                bmonth =  str((bdate+relativedelta(months=+1)).strftime('%B').lower())
            print ('Derived Month: '+bmonth)
            if bmonth != 'january':
                byear = str(bdate.year)
            else:
                byear = str(bdate.year + 1)

            # Call a function which if given the bagger_name would return bagger id from hr.employee
            # If bagger not in hr.employee, would create it before returning id
            # it also creates a contract for new bagger
            bagger_hr_id = get_bagger(bagger_name)
            assert bagger_hr_id,'bagger_hr_id not valid'
            bagger_obj = models.execute_kw(db, uid, password, 'fido.bagger', 'search_read', \
                        [[['name', '=', bagger_hr_id], ['x_year', '=', byear],['x_month', '=', \
                            bmonth]]], {'fields': ['id','bagger_line_ids']})

            if not bagger_obj:
                # Create bagger record in db
                bagger_id = models.execute_kw(db, uid, password, 'fido.bagger', 'create', \
                                  [{'name': bagger_hr_id, 'x_month': bmonth,'x_year': byear}])
                assert bagger_id,'bagger record creation failed in fido.bagger'
            else:
                bagger_id = bagger_obj[0]['id']
            assert bagger_id,'no valid bagger_id'
            bagger_obj = models.execute_kw(db, uid, password, 'fido.bagger', 'search_read', \
                                           [[['name', '=', bagger_hr_id], ['x_year', '=', byear], ['x_month', '=', \
                                                                                                   bmonth]]],
                                           {'fields': ['id', 'bagger_line_ids']})

            for id in bagger_obj[0]['bagger_line_ids']:
                bagger_line = models.execute_kw(db, uid, password, 'fido.bagger.line', 'search_read', \
                                               [[['id', '=', id]]],
                                               {'fields': ['fido_date', 'x_quantity']})
                if bagger_line[0]['fido_date'] == bdate.strftime('%Y-%m-%d'):
                    raise Exception('Date Already Exists in this bagger Record')


            # Insert record
            line_ids = [(0,0,{'fido_date': bdate.strftime('%Y-%m-%d'),
                            'x_quantity': qty
                          })]

            # Create Bagger Line ids
            bagger_line =models.execute_kw(db, uid, password, 'fido.bagger', 'write', [[bagger_id], {\
                            'bagger_line_ids': line_ids}])

            assert bagger_line,'Bagger Line Id creation failed'
            print 'Bagger Line record created for: ' + str([bagger_name,bdate,qty])
            bagger_totals = bagger_totals + int(qty)
            sn = sn + 1
            outstr = str(sn)+','+bagger_name+','+str(qty)+','+bmonth+','+bdate.strftime('%Y.%m.%d')+','+str(byear)

            outfile.write(outstr+'\n')
        except Exception as e:
            print 'Bagger Update Error.' + str(e)
            esn = esn + 1
            errstr = str(esn)+','+bagger_name+','+str(qty)+','+bmonth+','+str(bdate.strftime('%Y.%m.%d'))+','+str(byear)+',"'+ str(e)+'"'
            errfile.write(errstr+'\n')
            # raise

print 'Total Bags: '+ "{:,}".format(bagger_totals)
print str(sn) + ' Records Successful'
print str(esn) + ' Records Failed'
total_rec = sn + esn
if total_rec != 0:
    fr = (esn)/float(sn+esn)*100
else:
    fr = 0
print 'FAIL RATE: ' +"{:5,.2f}".format(fr)+'%'
print 'SUCCESS FILE: '+OUTF
print 'ERROR FILE: '+ERRF

errfile.close()
outfile.close()