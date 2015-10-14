from __future__ import division
from simple_salesforce import Salesforce
import config
import json
import dateparser
from frozendict import frozendict
import win32com.client


def fileToStr(fileName):
    """Return a string containing the contents of the named file."""
    fin = open(fileName)
    contents = fin.read()
    fin.close()
    return contents


def jsonizer(rawdata):
    """pretty prints SOQL dumps.
    Run through this and then json.loads() to smooth data."""
    jsondata = json.dumps(
        rawdata,
        sort_keys=True,
        indent=4,
        separators=(',', ': ')
    )
    return jsondata


def prettyQuery(query):
    """prints JSON of SOQL query. For console use."""
    sf = Salesforce(username=config.username,
                    password=config.password,
                    security_token=config.security_token)
    raw = sf.query_all(query)
    pretty = jsonizer(raw)
    print pretty


def nestedGet(checkFields, sourceDict):
    """deep dives into a nested dict. checkFields is the hierarchy to
    traverse."""
    return reduce(dict.__getitem__, checkFields, sourceDict)


class TeamMember:
    """convenience object"""
    def __init__(self, name):
        self.name = name
        self.caseCount = set()
        self.rfcCount = set()
        self.closedCount = set()
        self.tdCount = set()


class RFCReport:
    def __init__(self):
        print "Logging in to Salesforce API..."
        # initialize our SFDC connection
        self.sf = Salesforce(username=config.username,
                             password=config.password,
                             security_token=config.security_token)
        self.closerTeam = dict()
        self.listedUsers = dict()
        self.caseData = None
        self.filteredCases = None
        self.reportData = dict()
        self.message = ""
        self.fulltable = ''
        self.oldestdate = None
        self.newestdate = None
        print "Login successful."

    def getData(self, initString, query, checkFields, exitString):
        """ Generalized case data querying function.
        Returns nested dict/list structure corresponding to SOQL output.
        Query should be a SOQL query.
        checkFields should be an ordered list of fields to drill down
        through to reach a unique case ID or case number within the query used.
        For example, our case query returns Parent.CaseNumber,
        which is represented in the jsonized output as a value within the
        Parent dict within the Record dict representing each change. This
        means that we need to drill "records" > (list, must be iterated) >
        "Parent" > "CaseNumber".
        The "records" part and the unindexed list following it are assumed
        and handled automatically in this func, so the correct
        checkFields will be ["Parent", "CaseNumber"]."""
        print initString
        data = self.sf.query_all(query)
        output = json.loads(jsonizer(data))
        lengthset = set()
        for change in output["records"]:
            lengthset.add(nestedGet(checkFields, change))
        totalcase = len(lengthset)
        print "Got", totalcase, exitString
        return output

    def genReport(self, data):
        """deduplicate gathered case data"""
        dupecount = 0
        output = dict()
        for change in data["records"]:
            for line in change["FeedTrackedChanges"]["records"]:
                if line["NewValue"] in ("Ready For Close", "Closed"):
                    caseid = nestedGet(["Parent", "CaseNumber"], change)
                    changedate = dateparser.parse(change["CreatedDate"])
                    if self.oldestdate is None:
                        self.oldestdate = changedate
                    if self.newestdate is None:
                        self.newestdate = changedate
                    if changedate > self.newestdate:
                        self.newestdate = changedate
                    if changedate < self.oldestdate:
                        self.oldestdate = changedate
                    # need to account for more than one t2 on a case
                    if caseid in output:
                        # chronological order - latest gets it
                        if output[caseid]["Date"] > changedate:
                            dupecount += 1
                            continue
                    if nestedGet(["Parent", "Cancel_Effective_Date__c"],
                                 change) is not None:
                        teardown = True
                    else:
                        teardown = False
                    output[caseid] = frozendict(
                        Name=nestedGet(["CreatedBy", "Name"], change),
                        Case=caseid,
                        Status=line["NewValue"],
                        Teardown=teardown,
                        Date=changedate)
        print "Found and removed", dupecount, "cases handled more than " \
                                              "once."
        print "Credit for duplicates given to latest resolver."
        return output

    def sumReport(self):
        """generate summaries of gathered data"""
        print "Generating summaries..."
        for case in self.reportData.itervalues():
            name = case["Name"]
            if name not in self.listedUsers:
                self.listedUsers[name] = TeamMember(name)
            nameobj = self.listedUsers[name]
            nameobj.caseCount.add(case)
            if case["Status"] == "Ready For Close":
                nameobj.closedCount.discard(case)
                nameobj.rfcCount.add(case)
            if case["Status"] == "Closed":
                nameobj.closedCount.add(case)
                nameobj.rfcCount.discard(case)
            if case["Teardown"]:
                nameobj.tdCount.add(case)
                nameobj.rfcCount.discard(case)
                nameobj.closedCount.discard(case)

    def printReport(self):
        """calculate offsets for HTML table rows and generate full table"""
        print "Reticulating splines..."
        sorted_list = sorted(self.listedUsers.itervalues(),
                             key=lambda x: len(x.caseCount), reverse=True)
        cMax = len(sorted_list[0].caseCount)
        for each in sorted_list:
            agentname = each.name
            cases = len(each.caseCount)
            casesadj = int((cases / cMax) * 400)
            if casesadj == 400:
                casesadj = 390
            casesrem = 400 - casesadj
            rfcs = len(each.rfcCount)
            rfcsadj = int((rfcs / cMax) * 400)
            if rfcsadj == 400:
                rfcsadj = 390
            rfcsrem = 400 - rfcsadj
            selfs = len(each.closedCount)
            selfadj = int((selfs / cMax) * 400)
            if selfadj == 400:
                selfadj = 390
            selfrem = 400 - selfadj
            tds = len(each.tdCount)
            tdsadj = int((tds / cMax) * 400)
            if tdsadj == 400:
                tdsadj = 390
            tdsrem = 400 - tdsadj
            bodypart = fileToStr("tablerow.html").format(**locals())
            self.fulltable += bodypart

    def sendEmail(self):
        fulltable = self.fulltable
        daterange = ' - '.join((str(self.oldestdate.strftime("%B %d, %Y")),
                                str(self.newestdate.strftime("%B %d, %Y"))))
        tablemoz = config.tablemoz
        emailbody = fileToStr("email.html").format(**locals())
        olMailItem = 0x0
        obj = win32com.client.Dispatch("Outlook.Application")
        email = obj.CreateItem(olMailItem)
        email.Subject = "Escalation Support Activity"
        email.HTMLBody = emailbody
        email.to = config.sendMailTo
        email.Send()

supportInit = ''.join((
    "Querying all Support SFDC cases since start of ",
    config.SFDCdaterange, "..."
))

if __name__ == "__main__":
    print "==TPS Report v2=="
    # main execution steps
    newreport = RFCReport()
    supportQuery = ''.join((
        "SELECT CreatedBy.Name, ",
        "CreatedDate, ",
        "Parent.CaseNumber, ",
        "Parent.Cancel_Effective_Date__c, ",
        "(SELECT NewValue, FieldName ",
        "from FeedTrackedChanges) ",
        "from CaseFeed ",
        "WHERE (Parent.LastModifiedDate >= ",
        config.SFDCdaterange,
        " AND CreatedBy.UserRoleId = '",
        config.reportrole, "'",
        " AND CreatedDate = ",
        config.SFDCdaterange, ")"
    ))
    newreport.caseData = newreport.getData(
        initString=supportInit,
        query=supportQuery,
        checkFields=["Parent", "CaseNumber"],
        exitString="total closed/RFC Support cases")
    newreport.reportData = newreport.genReport(newreport.caseData)
    newreport.sumReport()
    newreport.printReport()
    newreport.sendEmail()
