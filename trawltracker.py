import datetime
import json
import os
import urllib

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

DEFAULT_REPORT_COLLECTION_NAME = 'default_report_collection'

# We set a parent key on the 'Reports' to ensure that they are all in the same
# entity group. Queries across the single entity group will be consistent.
# However, the write rate should be limited to ~1/second.


# TODO(jason): I'm only using the default report collection for now. I'm
# guessing the constant can just be the Key itself?
def report_collection_key(
        report_collection_name=DEFAULT_REPORT_COLLECTION_NAME):
    """Contructs a Datastore key for a Report Collection."""
    return ndb.Key('ReportCollection', report_collection_name)

class Report(ndb.Model):
    """Models a single report of a spotted trawler."""
    date = ndb.DateTimeProperty()
    location = ndb.GeoPtProperty()
    photo = ndb.BlobProperty()
    comment = ndb.TextProperty()

class Image(webapp2.RequestHandler):
    def get(self):
        report = Report.get_by_id(int(self.request.get('img_id')),
                                  parent=report_collection_key())
        if report.photo:
            self.response.headers.add_header('Access-Control-Allow-Origin', '*')
            self.response.headers['Content-Type'] = 'image/png'
            self.response.out.write(report.photo)
        else:
            self.error(404)


class ReportsViewPage(webapp2.RequestHandler):

    def get(self):
        reports_to_output = reports_as_dicts()
        template_values = {
            'reports': reports_to_output,
        }

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))


def reports_as_dicts():
    reports_to_output = []
    reports_query = Report.query(ancestor=report_collection_key(
        DEFAULT_REPORT_COLLECTION_NAME)).order(-Report.date)
    for report in reports_query.fetch(100):
        report_to_output = {}

        # TODO(jason): timezones...
        report_to_output['date'] = report.date.strftime('%d/%m/%Y %H:%M')
        report_to_output['lat'] = report.location.lat
        report_to_output['long'] = report.location.lon
        report_to_output['comment'] = report.comment
        if report.photo:
            path_to_img = 'img?img_id=%s' % report.key.id()
            report_to_output['path_to_img'] = path_to_img
        reports_to_output.append(report_to_output)
    return reports_to_output

class GetReports(webapp2.RequestHandler):
    def get(self):
        reports_to_output = reports_as_dicts()
        self.response.headers.add_header('Access-Control-Allow-Origin', '*')
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(reports_to_output))


class ReportEntryPage(webapp2.RequestHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template('entry.html')
        self.response.write(template.render({}))


class SubmitReport(webapp2.RequestHandler):
    """Handler for report submission.

    The request should have the following parameters:
      date: Float Epoch timestamp of this report, in seconds.
      lat: Latitude, as a float.
      long: Longitude, as a float.
      text: Additional text/comments.
    """

    def post(self):
        # We set the same parent key on the 'Greeting' to ensure each Greeting
        # is in the same entity group. Queries across the single entity group
        # will be consistent. However, the write rate to a single entity group
        # should be limited to ~1/second.
        report_collection_name = self.request.get(
            'report_collection_name', DEFAULT_REPORT_COLLECTION_NAME)
        report = Report(parent=report_collection_key(report_collection_name))
        report.date = datetime.datetime.fromtimestamp(
            float(self.request.get('date')))
        report.location = ndb.GeoPt(
            '%s, %s' % (self.request.get('lat'), self.request.get('long')))
        request_photo = self.request.get('img')
        report.photo = str(request_photo)
        report.comment = self.request.get('comment')
        report.put()
        self.redirect('/')


application = webapp2.WSGIApplication([
    ('/', ReportsViewPage),
    ('/entry', ReportEntryPage),
    ('/getreports', GetReports),
    ('/img', Image),
    ('/submit', SubmitReport),
], debug=True)
