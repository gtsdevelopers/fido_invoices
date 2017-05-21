import xmlrpclib
from datetime import datetime
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
    db = 'fidodb'
    username = 'admin'
    password = 'admin'
    port = '8069'
    host = 'localhost'
    url = 'http://%s:%s' % (host, port)
    models = xmlrpclib.ServerProxy('%s/xmlrpc/2/object' % (url))
    common = xmlrpclib.ServerProxy('{}/xmlrpc/2/common'.format(url))
    uid = common.authenticate(db, username, password, {})

    assert uid,'com.login failed'
    version = common.version()
    assert version['server_version'] == '10.0','Server not 10.0'
except Exception, e:
    print version['server_version'],str(e)
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
    # creates a bagger if not exist in hr.employee and return bagger_id
    try:

        bagger_hr_obj = models.execute_kw(db, uid, password, 'hr.employee', 'search_read', \
                         [[['name', '=', baggername]]], {'fields': ['id']})
        if not bagger_hr_obj:
            # Create Bagger in hr.employee
            jobid = models.execute_kw(db, uid, password, 'hr.job', 'search_read', \
                            [[['name', '=', 'Bagger']]], {'fields': ['id']})
            assert jobid,'no jobid found for job Bagger'
            print 'JOB ID: ' + str(jobid)
            bagger_hr = models.execute_kw(db, uid, password, 'hr.employee', 'create',\
                                          [{'name': baggername,'job_id': jobid[0]['id']}])
            assert bagger_hr,'Bagger Creation Fails'
        else:
            bagger_hr = bagger_hr_obj[0]['id']
        return bagger_hr
    except Exception, e:
        print 'get_bagger() Error:\n' +  str(e)
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
            qty = row['QTY'].strip()
            if not qty:
                qty = 0

            bmonth = row['MONTH'].strip().lower()
            bdate = datetime.strptime(row['DATE'].strip(), '%Y.%m.%d')
            if bmonth != 'January':
                byear = str(bdate.year)
            else:
                byear = str(bdate.year + 1)

            # Call a function which if given the bagger_name would return bagger id from hr.employee
            # If bagger not in hr.employee, would create it before returning id
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
            print str(bagger_obj)
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
            print 'Bagger id: ' +str(bagger_id)
            # Create Bagger Line ids
            bagger_line =models.execute_kw(db, uid, password, 'fido.bagger', 'write', [[bagger_id], {\
                            'bagger_line_ids': line_ids}])

            assert bagger_line,'Bagger Line Id creation failed'
            bagger_totals = bagger_totals + int(qty)
            sn = sn + 1
            outstr = str(sn)+','+bagger_name+','+str(qty)+','+bmonth+','+bdate.strftime('%Y.%m.%d')+','+str(byear)

            outfile.write(outstr+'\n')
        except Exception as e:
            print 'Bagger Update Error.' + str(e)
            esn = esn + 1
            errstr = str(esn)+','+bagger_name+','+str(qty)+','+bmonth+','+str(bdate.strftime('%Y.%m.%d'))+','+str(byear)+',"'+ str(e)+'"'
            errfile.write(errstr+'\n')
            raise

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