.. conversationalist documentation master file, created by
   sphinx-quickstart on Mon Apr 11 18:30:56 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to conversationalist's documentation!
=============================================

Contents:

.. toctree::
   :maxdepth: 2

   classes
   utils


Configuration
-------------

Expects ``~/conversationalist/json`` and ``~/conversationalist/content`` directories will be
available for file-writing.

Testing
-------

Install ``pytest`` in your python environment.  Clone the ``conversationalits`` repository.
Then run ``py.test`` from the top-level of the repository clone.

Date Parsing
------------

The twitter API returns the following datetime format for temporal fields such
 as ``created_at``::

      "created_at": "Wed May 23 06:01:13 +0000 2007",

When transforming twitter API responses into ``Status`` objects, the ``tweepy`` library
uses the standard python ``email.utils`` module's datetime parser utilities.

The twitter format approximates the RFC 2822 date and time specification. From the specification::

    The date and time-of-day SHOULD express local time.

    The zone specifies the offset from Coordinated Universal Time (UTC,
    formerly referred to as "Greenwich Mean Time") that the date and
    time-of-day represent.  The "+" or "-" indicates whether the
    time-of-day is ahead of (i.e., east of) or behind (i.e., west of)
    Universal Time.  The first two digits indicate the number of hours
    difference from Universal Time, and the last two digits indicate the
    number of minutes difference from Universal Time.  (Hence, +hhmm
    means +(hh * 60 + mm) minutes, and -hhmm means -(hh * 60 + mm)
    minutes).  The form "+0000" SHOULD be used to indicate a time zone at
    Universal Time.  Though "-0000" also indicates Universal Time, it is
    used to indicate that the time was generated on a system that may be
    in a local time zone other than Universal Time and therefore
    indicates that the date-time contains no information about the local
    time zone.

The "+0000" zone indicates that the API is returning time in UTC.

Parsing the Twitter API's 'created_at' fields
.............................................


When creating ``Status`` objects from the text responses sent by the Twitter API, the ``tweepy`` library
reads the ``created_at`` field from the data for a status, and then sends the temporal string formatted
with the RFC 2822 specification to a utility function that generates
a Python datetime object after calling the ``email.utils.parsedate`` function with the temporal string. Here's the
``tweepy`` utility function::

  def parse_datetime(string):
      return datetime(*(parsedate(string)[:6]))

As you can see, the ``tweepy`` function does not pass a timezone.  The ``parsedate`` function *does* apply
the offset specified (though the twitter API responds in UTC, so there is no offset). The ``parsedate`` function
returns a tuple values, which then gets sliced for its first six values, which happen to be year, month, day, hour,
minute, second. The naive datetime that is then instantiated has UTC data, but is not instantiated with
timezone info.

Parsing dates from timeline JSON
................................

The :func:`~.utils.json_to_conversation` function parses ``Timeline`` objects encoded in JSON. The
function relies on the `date-util` project's ``parse`` utility function to transform the ``start`` and
``cutoff`` properties of JSON objects into Python datetime objects.  Timeline datetimes are encoded
into ISO8601, which the ``parse`` utility function reads; the ``parse`` function transfers te ISO8601
UTC offset into the Python datetime object's ``tzinfo`` with a ``tzoffset``.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

