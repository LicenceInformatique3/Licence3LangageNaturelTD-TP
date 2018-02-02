#!/usr/bin/python
# -*- coding:UTF-8 -*-

################################################################################
#
# Copyright 2010-2014 Carlos Ramisch, Vitor De Araujo, Silvio Ricardo Cordeiro,
# Sandra Castellanos
#
# webFreq.py is part of mwetoolkit
#
# mwetoolkit is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# mwetoolkit is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with mwetoolkit.  If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
"""
This module provides the `WebFreq` class. This class represents an
abstract gateway that allows you to access the a web search index and look
up for the number of web pages that contain a certain word or ngram.
"""






import sys
import pickle # Cache is pickled to/from a file
from datetime import date
import urllib.request, urllib.error, urllib.parse
import urllib.request, urllib.parse, urllib.error
import time

MAX_CACHE_DAYS = -1
DEFAULT_LANG = "en"
################################################################################

class WebFreq( object ) :
    """
    The `WebFreq` class is an abstraction that allows you to call a search
    engine Web Service search to estimate the frequency of a certain search
    term in the Web, in terms of pages that contain that term (a term not in
    the sense of Terminology, but in the sense of word or ngram, i.e. an
    Information Retrieval term). After instanciated, you should call the
    `search_frequency` function to obtain these estimators for a given
    term. This class should not be used directly, but through the subclasses
    `YahooFreq`, `GoogleFreq` and `GoogleFreqUniv`.

    N.B.: Yahoo is not supported anymore, after August 2011.
    """

################################################################################

    def __init__(self, cache_filename, url, post_data, treat_result,
                 max_cache_days=MAX_CACHE_DAYS):
        """
        Instantiates a connection to the a Web Search service. This object
        is a gate through which you can estimate the number of times a given
        element (word or ngram) appears in the Web. A cache mechanism does
        automatically manage repeated queries. The additional parameters
        will be used to chose a search engine (currently, Google and Yahoo
        are supported)
        N.B.: Yahoo is not supported anymore, after August 2011.

        @param cache_filename The string corresonding to the name of the
        cache file in/from which you would like to store/retrieve recent
        queries. You should have write permission in the current directory
        in order to create and update the cache file.

        @param url The URL of the web service that allows access to the
        search engine index. The URL is generally in the provider's
        documentation.

        @param post_data Some providers like google ask for special fields
        to be sent as post data to identify the user.

        @param treat_result A callback function that will treat the result
        of the search engine query. Since Google and Yahoo differ in the
        format of the answer (names and structure of fields in json format),
        it is necessary to personalise the treatment. The callback should
        receive a json dictionary and return an integer.

        @param max_days Maximum number of days since cache entry was updated
         If the entry is older than `max_days` days, the search engine will
         be consulted again and cache will be updated. Default=-1 (no limit)

        @return A new instance of the `WebFreq` service abstraction.
        """
        self.url = url
        self.post_data = post_data
        self.treat_result = treat_result
        self.cache_filename = cache_filename
        #### CACHE MECHANISM ####
        self.max_cache_days = max_cache_days
        self.today = date.today()
        self.cache_file = None
        try :
            cache_file = open( self.cache_filename, "rb" )
            self.cache = pickle.load( cache_file, encoding="bytes" )
            cache_file.close()
        except (IOError, EOFError) :
            cache_file = open( self.cache_filename, "wb" )
            cache_file.close()
            self.cache = {}
        self.cache_modified = False


################################################################################

    def send_query( self, lang, search_term ):
        """
        Sends the query to the search engine by replacing the placeholders
        in the template url and creating a new request through urllib2.

        @param lang The language code of the search

        @param search_term The search term corresponding to the query. The
        search term must be quoted if you want an exact search. The search
        term should not be escaped, this is done inside this function.

        @return The integer corresponding to the frequency of the query term
        in the web according to that search engine
        """
        url = self.url.replace( "LANGPLACEHOLDER",lang )
        url = url.replace( "QUERYPLACEHOLDER", urllib.parse.quote_plus( search_term ))
        request = urllib.request.Request( url, None, self.post_data )
        response = urllib.request.urlopen( request )
        response_string = response.read()
        return self.treat_result( response_string )

################################################################################

    def search_frequency( self, in_term, lang="en" ) :
        """
        Searches for the number of Web pages in which a given `in_term`
        occurs, according to a search index. The search is case insensitive
        and language-dependent, please remind to define the correct
        `--lang` option in `counter.py`. If the frequency of the `in_term`
        is still in cache and the cache entry is not expired, no Web query
        is performed. Since each query can take up to 3 or 4 seconds,
        depending on your Internet connection, cache is very important.
        Please remember to define the correct `--max-cache-days` option in
        `counter.py` according to the number of queries you would like to
        perform.

        @param in_term The string corresponding to the searched word or
        ngram. If a sequence of words is searched, they should be separated
        by spaces as in a Web search engine query. The query is also
        performed as an exact term query, i.e. with quote marks around the
        terms. You can use a wildcard to replace a whole word, since
        search engines provide wildcarded query support.

        @param lang Two-letter code of the language of the web pages the
        search engine should consider. Making language-independent queries
        does not seem a good idea since the counters will be overestimated.
        Default is "en" for English.

        @return An integer corresponding to an approximation of the number
        of Web pages that contain the searched `in_term`. This frequency
        approximation can estimate the number of times the term occurs if
        you consider the Web as a corpus.
        """
        term = in_term.lower().strip()
        # Look into the cache
        count = self.lookup_cache(lang, term)
        if count is not None :
            return count
        else : # Must re-execute web query
            search_term = "\"" + term + "\""
            #if isinstance( search_term, unicode ) :
            #    search_term = search_term.encode( 'utf-8' )
            #search_term = "\"" + search_term + "\""
            tries = 0
            max_tries = 5
            result_count = None
            while result_count is None :
                try:
                    tries = tries + 1
                    result_count = self.send_query( lang, search_term )
                    if result_count is None :
                        print("ERROR: Probably your daily quota was reached",
                                  file=sys.stderr)
                        sys.exit(-1)
                        #raise Exception("Result was None for term {}".format(search_term))
                except urllib.error.HTTPError as err:
                    print( "Got an error ->" + str( err ), file=sys.stderr)
                    if tries < max_tries :
                        print("Will retry in 30s...", file=sys.stderr)
                        time.sleep( 30 )
                    else :
                        print("Stopped at search term: " + search_term,
                              file=sys.stderr)
                        if err.code == 403 : #Forbidden
                            print("Probably your ID for the Google university "
                                  "research program is not correct or is "
                                  "associated to another IP address",
                                  file=sys.stderr)
                            print("Check \"http://research.google.com/"
                                  "university/search/\" for further "
                                  "information",file=sys.stderr)
                        print("PLEASE VERIFY YOUR INTERNET CONNECTION",
                              file=sys.stderr)
                        sys.exit( -1 )
            self.add_to_cache(lang, term, result_count )
            return result_count

################################################################################

    def build_cache_key(self, lang, term):
        return "___".join([lang,term])

################################################################################

    def lookup_cache(self, lang, term):
        """
        Returns the count of `term` in `lang` from cache, or None if absent or
        expired.
        @param lang: String with language code of `term`
        @param term: The query term used to obtain the `count`
        @return: Integer count of looked up entry, `None` if absent/expired
        """
        cache_key = self.build_cache_key(lang, term)
        (freq, time_searched) = self.cache.get( cache_key , (None,None))
        if freq is None : # absent from cache
            return None
        dayspassed = self.today - time_searched
        if dayspassed.days >= self.max_cache_days and self.max_cache_days >= 0 :
            return None # TTL expired, must search again :-(
        else :
            return freq # TTL not expired :-)

################################################################################

    def add_to_cache(self, lang, term, count ):
        """
        Add the `count` of a `term` string in language `lang` to the cache file
        @param lang: String with language code of `term`
        @param term: The query term used to obtain the `count`
        @param count: The integer count returned by the search engine
        """
        cache_key = self.build_cache_key(lang, term)
        self.cache[ cache_key ] = (count, self.today)
        self.cache_modified = True

################################################################################

    def flush_cache( self ) :
        """
        Explicit destructor, flushes the cache content to a file before
        closing the connection. Thus, the cache entries will be available
        the next time the search engine is called and, if they are not
        expired, will avoid repeated queries.

        IMPORTANT: If you want the cache mechanism to be used properly,
        NEVER FORGET to call this function in a "finally" block, in order
        to guarantee that, even if an exceptioon occurs (like pressing
        Ctrl+C), the cache will be flushed.
        """
        # Flush cache content to file
        if self.cache_modified :
            cache_file = open( self.cache_filename, "w" )
            pickle.dump( self.cache, cache_file )
            cache_file.close()
