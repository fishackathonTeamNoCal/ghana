import base64
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
    vessel_id = ndb.StringProperty()
    photo = ndb.BlobProperty()
    comment = ndb.TextProperty()
    heading = ndb.StringProperty()
    location_typed = ndb.StringProperty()
    date_time_typed = ndb.StringProperty()

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
        if report.location:
            report_to_output['lat'] = report.location.lat
            report_to_output['long'] = report.location.lon
        report_to_output['vessel_id'] = report.vessel_id
        report_to_output['comment'] = report.comment
        if report.photo:
            path_to_img = 'img?img_id=%s' % report.key.id()
            report_to_output['path_to_img'] = path_to_img
        report_to_output['heading'] = report.heading
        report_to_output['location_typed'] = report.location_typed
        report_to_output['date_time_typed'] = report.date_time_typed
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

    The request can have the following parameters:
      date: Float Epoch timestamp of this report, in seconds.
      lat: Latitude, as a float.
      long: Longitude, as a float.
      vessel_id: String
      img: the photo image. At most one of img or encodedImg should be set.
      encodedImg: the base64 encoded photo image. At most one of img or
          encodedImg should be set.
      comment: Additional text/comments.
      heading: String input describing the trawler's direction.
      location_typed: user-typed location (in case GPS was unavailable)
      date_time_typed: user-typed date and time (if they chose to provide
          something other than the current time)    
    """

    def post(self):
        report_collection_name = self.request.get(
            'report_collection_name', DEFAULT_REPORT_COLLECTION_NAME)
        report = Report(parent=report_collection_key(report_collection_name))
        request_date = self.request.get('date')
        if request_date:
            report.date = datetime.datetime.fromtimestamp(float(request_date))
        lat = self.request.get('lat')
        lon = self.request.get('long')
        if lat and lon:
            report.location = ndb.GeoPt(
                '%s, %s' % (self.request.get('lat'), self.request.get('long')))
        report.vessel_id = self.request.get('vessel_id')
        request_photo = self.request.get('img')
        if request_photo:
            report.photo = str(request_photo)
        else:
            encoded_image = self.request.get('encodedImg')
            if encoded_image:
                report.photo = base64.b64decode(encoded_image)
        report.heading = self.request.get('heading')
        report.location_typed = self.request.get('location_typed')
        report.date_time_typed = self.request.get('date_time_typed')
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
