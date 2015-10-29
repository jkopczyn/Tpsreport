from __future__ import division
from simple_salesforce import Salesforce
import config
import json
import dateparser
from frozendict import frozendict
import webbrowser
from collections import OrderedDict


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
    """prints JSON of SOQL query. For convenience console use."""
    sf = Salesforce(username=config.username,
                    password=config.password,
                    security_token=config.security_token)
    raw = sf.query_all(query)
    pretty = jsonizer(raw)
    print pretty
    return pretty


def nestedGet(checkFields, sourceDict):
    """deep dives into a nested dict. checkFields should be an ordered list
    of fields to drill down through to reach a unique case ID or case number
    within the query used. For example, our case query returns
    Parent.CaseNumber, which is represented in the jsonized output as a value
    within the Parent dict within the Record dict representing each change.
    This means that we need to drill "records" > (list, must be iterated) >
    "Parent" > "CaseNumber". This method cannot traverse lists/unindexed
    literals, so I've built handing "for x in dict["records"] into the
    various functions that use it. Therefore, what we want for our
    checkFields is ["Parent", "CaseNumber"]."""
    return reduce(dict.__getitem__, checkFields, sourceDict)


class TeamMember(object):
    """convenience object"""

    def __init__(self, name):
        self.name = name
        self.caseCount = set()
        self.rfcCount = set()
        self.closedCount = set()
        self.tdCount = set()
        self.counts = OrderedDict([("Ready for Close", self.rfcCount),
                                   ("Teardowns", self.tdCount),
                                   ("Self-Closed", self.closedCount)])


class RFCReport:
    def __init__(self):
        print "Logging in to Salesforce API..."
        # initialize our SFDC connection
        self.sf = Salesforce(username=config.username,
                             password=config.password,
                             security_token=config.security_token)
        self.caseData = None
        self.reportData = dict()
        self.fulltable = ''
        self.outputDict = dict()
        self.sorted_list = list()
        print "Login successful."

    def getData(self, initString, query, checkFields, exitString):
        """ Generalized case data querying function.
        Returns nested dict/list structure corresponding to SOQL output.
        Query should be a SOQL query. See nestedGet for checkFields format."""
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
                if line is not None:
                    if line["NewValue"] in (
                            "Ready For Close",
                            "Closed",
                            "Cancelled",
                            "Closed as Duplicate"):
                        caseid = nestedGet(["Parent", "CaseNumber"], change)
                        changedate = dateparser.parse(change["CreatedDate"])
                        # need to account for >1 escalation per case
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
        print "Found and removed", dupecount, "cases handled more than once."
        print "Credit for duplicates given to latest resolver."
        return output

    def tabulateReport(self):
        """tabulates case data per team member"""
        print "Reticulating splines..."
        listedUsers = [TeamMember(y) for y in
                       set([x["Name"] for x in self.reportData.itervalues()])]
        print "Generating summaries..."
        for case in self.reportData.itervalues():
            name = case["Name"]
            nameobj = (filter(lambda z: z.name == name, listedUsers))[0]
            nameobj.caseCount.add(case)
            if case["Status"] == "Ready For Close":
                nameobj.closedCount.discard(case)
                nameobj.rfcCount.add(case)
            if case["Status"] in (
                    "Closed",
                    "Cancelled",
                    "Closed as Duplicate"):
                nameobj.closedCount.add(case)
                nameobj.rfcCount.discard(case)
            if case["Teardown"]:
                nameobj.tdCount.add(case)
                nameobj.rfcCount.discard(case)
                nameobj.closedCount.discard(case)
        self.sorted_list = sorted(listedUsers,
                                  key=lambda q: len(q.caseCount),
                                  reverse=True)

    def updateJSON(self):
        cutoff = ''
        if config.closedOnly:
            cutoff = "resolved cases only"
        d = [x["Date"] for x in self.reportData.itervalues()]
        dates = ' - '.join(
            [x.strftime("%B %d, %Y") for x in (min(d), max(d))])
        drange = ' '.join(
            ["current" if x == "this" else x for x in
             (config.SFDCdaterange.lower().split('_'))])

    @property
    def dataToJSON(self):
        rowset = [['Total', ], ]
        groups = list()
        categories = list()
        for each in self.sorted_list:
            categories.append(each.name)
            subrow = [len(each.caseCount), ]
            for key, value in each.counts.iteritems():
                subrow.append(len(value))
                if key not in rowset[0]:
                    rowset[0].append(key)
                    groups.append(key)
            rowset.append(subrow)
        self.outputDict = dict(rows=rowset,
                               groups=groups,
                               categories=categories)
        return jsonizer(self.outputDict)


supportInit = ''.join((
    "Querying all non-open Support SFDC cases since start of ",
    config.SFDCdaterange, "..."
))

if __name__ == "__main__":

    closedCut = ')'
    statusString = 'Escalations-involved cases'
    if config.closedOnly:
        closedCut = ''.join((" AND (Parent.Status = 'Closed' ",
                             "OR Parent.Status = 'Ready For Close' ",
                             "OR Parent.Status = 'Cancelled' ",
                             "OR Parent.Status = 'Closed as Duplicate'))"))
        statusString = 'Resolved Escalations-involved cases'

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
        config.SFDCdaterange,
        closedCut
    ))
    newreport.caseData = newreport.getData(
        initString=supportInit,
        query=supportQuery,
        checkFields=["Parent", "CaseNumber"],
        exitString=statusString)
    newreport.reportData = newreport.genReport(newreport.caseData)
    newreport.tabulateReport()
    with open('scripts\\testdata.json', 'w') as foutput:
        foutput.write(newreport.dataToJSON)
    webbrowser.open_new("http://127.0.0.1:8887/index.html")
