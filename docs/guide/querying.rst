=====================
Querying the database
=====================
:class:`~mongoengine.Document` classes have an :attr:`objects` attribute, which
is used for accessing the objects in the database associated with the class.
The :attr:`objects` attribute is actually a
:class:`~mongoengine.queryset.QuerySetManager`, which creates and returns a new
:class:`~mongoengine.queryset.QuerySet` object on access. The
:class:`~mongoengine.queryset.QuerySet` object may be iterated over to
fetch documents from the database::

    # Prints out the names of all the users in the database
    for user in User.objects:
        print user.name

.. note::

    As of MongoEngine 0.8 the querysets utilise a local cache.  So iterating
    it multiple times will only cause a single query.

Filtering queries
=================
The query may be filtered by calling the
:class:`~mongoengine.queryset.QuerySet` object with field lookup keyword
arguments. The keys in the keyword arguments correspond to fields on the
:class:`~mongoengine.Document` you are querying::

    # This will return a QuerySet that will only iterate over users whose
    # 'country' field is set to 'uk'
    uk_users = User.objects(country='uk')

Fields on embedded documents may also be referred to using field lookup syntax
by using a double-underscore in place of the dot in object attribute access
syntax::

    # This will return a QuerySet that will only iterate over pages that have
    # been written by a user whose 'country' field is set to 'uk'
    uk_pages = Page.objects(author__country='uk')


Query operators
===============
Operators other than equality may also be used in queries; just attach the
operator name to a key with a double-underscore::

    # Only find users whose age is 18 or less
    young_users = Users.objects(age__lte=18)

Available operators are as follows:

* ``ne`` -- not equal to
* ``lt`` -- less than
* ``lte`` -- less than or equal to
* ``gt`` -- greater than
* ``gte`` -- greater than or equal to
* ``not`` -- negate a standard check, may be used before other operators (e.g.
  ``Q(age__not__mod=5)``)
* ``in`` -- value is in list (a list of values should be provided)
* ``nin`` -- value is not in list (a list of values should be provided)
* ``mod`` -- ``value % x == y``, where ``x`` and ``y`` are two provided values
* ``all`` -- every item in list of values provided is in array
* ``size`` -- the size of the array is
* ``exists`` -- value for field exists

String queries
--------------

The following operators are available as shortcuts to querying with regular
expressions:

* ``exact`` -- string field exactly matches value
* ``iexact`` -- string field exactly matches value (case insensitive)
* ``contains`` -- string field contains value
* ``icontains`` -- string field contains value (case insensitive)
* ``startswith`` -- string field starts with value
* ``istartswith`` -- string field starts with value (case insensitive)
* ``endswith`` -- string field ends with value
* ``iendswith`` -- string field ends with value (case insensitive)
* ``match``  -- performs an $elemMatch so you can match an entire document within an array


Geo queries
-----------

There are a few special operators for performing geographical queries. The following
were added in 0.8 for:  :class:`~mongoengine.fields.PointField`,
:class:`~mongoengine.fields.LineStringField` and
:class:`~mongoengine.fields.PolygonField`:

* ``geo_within`` -- Check if a geometry is within a polygon.  For ease of use
    it accepts either a geojson geometry or just the polygon coordinates eg::

        loc.objects(point__geo_with=[[[40, 5], [40, 6], [41, 6], [40, 5]]])
        loc.objects(point__geo_with={"type": "Polygon",
                                 "coordinates": [[[40, 5], [40, 6], [41, 6], [40, 5]]]})

* ``geo_within_box`` - simplified geo_within searching with a box eg::

        loc.objects(point__geo_within_box=[(-125.0, 35.0), (-100.0, 40.0)])
        loc.objects(point__geo_within_box=[<bottom left coordinates>, <upper right coordinates>])

* ``geo_within_polygon`` -- simplified geo_within searching within a simple polygon eg::

        loc.objects(point__geo_within_polygon=[[40, 5], [40, 6], [41, 6], [40, 5]])
        loc.objects(point__geo_within_polygon=[ [ <x1> , <y1> ] ,
                                                [ <x2> , <y2> ] ,
                                                [ <x3> , <y3> ] ])

* ``geo_within_center`` -- simplified geo_within the flat circle radius of a point eg::

        loc.objects(point__geo_within_center=[(-125.0, 35.0), 1])
        loc.objects(point__geo_within_center=[ [ <x>, <y> ] , <radius> ])

* ``geo_within_sphere`` -- simplified geo_within the spherical circle radius of a point eg::

        loc.objects(point__geo_within_sphere=[(-125.0, 35.0), 1])
        loc.objects(point__geo_within_sphere=[ [ <x>, <y> ] , <radius> ])

* ``geo_intersects`` -- selects all locations that intersect with a geometry eg::

        # Inferred from provided points lists:
        loc.objects(poly__geo_intersects=[40, 6])
        loc.objects(poly__geo_intersects=[[40, 5], [40, 6]])
        loc.objects(poly__geo_intersects=[[[40, 5], [40, 6], [41, 6], [41, 5], [40, 5]]])

        # With geoJson style objects
        loc.objects(poly__geo_intersects={"type": "Point", "coordinates": [40, 6]})
        loc.objects(poly__geo_intersects={"type": "LineString",
                                          "coordinates": [[40, 5], [40, 6]]})
        loc.objects(poly__geo_intersects={"type": "Polygon",
                                          "coordinates": [[[40, 5], [40, 6], [41, 6], [41, 5], [40, 5]]]})

* ``near`` -- Find all the locations near a given point::

        loc.objects(point__near=[40, 5])
        loc.objects(point__near={"type": "Point", "coordinates": [40, 5]})


    You can also set the maximum distance in meters as well::

        loc.objects(point__near=[40, 5], point__max_distance=1000)


The older 2D indexes are still supported with the
:class:`~mongoengine.fields.GeoPointField`:

* ``within_distance`` -- provide a list containing a point and a maximum
  distance (e.g. [(41.342, -87.653), 5])
* ``within_spherical_distance`` -- Same as above but using the spherical geo model
  (e.g. [(41.342, -87.653), 5/earth_radius])
* ``near`` -- order the documents by how close they are to a given point
* ``near_sphere`` -- Same as above but using the spherical geo model
* ``within_box`` -- filter documents to those within a given bounding box (e.g.
  [(35.0, -125.0), (40.0, -100.0)])
* ``within_polygon`` -- filter documents to those within a given polygon (e.g.
  [(41.91,-87.69), (41.92,-87.68), (41.91,-87.65), (41.89,-87.65)]).

  .. note:: Requires Mongo Server 2.0

* ``max_distance`` -- can be added to your location queries to set a maximum
  distance.


Querying lists
--------------
On most fields, this syntax will look up documents where the field specified
matches the given value exactly, but when the field refers to a
:class:`~mongoengine.fields.ListField`, a single item may be provided, in which case
lists that contain that item will be matched::

    class Page(Document):
        tags = ListField(StringField())

    # This will match all pages that have the word 'coding' as an item in the
    # 'tags' list
    Page.objects(tags='coding')

It is possible to query by position in a list by using a numerical value as a
query operator. So if you wanted to find all pages whose first tag was ``db``,
you could use the following query::

    Page.objects(tags__0='db')

If you only want to fetch part of a list eg: you want to paginate a list, then
the `slice` operator is required::

    # comments - skip 5, limit 10
    Page.objects.fields(slice__comments=[5, 10])

For updating documents, if you don't know the position in a list, you can use
the $ positional operator ::

    Post.objects(comments__by="joe").update(**{'inc__comments__$__votes': 1})

However, this doesn't map well to the syntax so you can also use a capital S instead ::

    Post.objects(comments__by="joe").update(inc__comments__S__votes=1)

    .. note:: Due to Mongo currently the $ operator only applies to the first matched item in the query.


Raw queries
-----------
It is possible to provide a raw PyMongo query as a query parameter, which will
be integrated directly into the query. This is done using the ``__raw__``
keyword argument::

    Page.objects(__raw__={'tags': 'coding'})

.. versionadded:: 0.4

Limiting and skipping results
=============================
Just as with traditional ORMs, you may limit the number of results returned, or
skip a number or results in you query.
:meth:`~mongoengine.queryset.QuerySet.limit` and
:meth:`~mongoengine.queryset.QuerySet.skip` and methods are available on
:class:`~mongoengine.queryset.QuerySet` objects, but the prefered syntax for
achieving this is using array-slicing syntax::

    # Only the first 5 people
    users = User.objects[:5]

    # All except for the first 5 people
    users = User.objects[5:]

    # 5 users, starting from the 10th user found
    users = User.objects[10:15]

You may also index the query to retrieve a single result. If an item at that
index does not exists, an :class:`IndexError` will be raised. A shortcut for
retrieving the first result and returning :attr:`None` if no result exists is
provided (:meth:`~mongoengine.queryset.QuerySet.first`)::

    >>> # Make sure there are no users
    >>> User.drop_collection()
    >>> User.objects[0]
    IndexError: list index out of range
    >>> User.objects.first() == None
    True
    >>> User(name='Test User').save()
    >>> User.objects[0] == User.objects.first()
    True

Retrieving unique results
-------------------------
To retrieve a result that should be unique in the collection, use
:meth:`~mongoengine.queryset.QuerySet.get`. This will raise
:class:`~mongoengine.queryset.DoesNotExist` if
no document matches the query, and
:class:`~mongoengine.queryset.MultipleObjectsReturned`
if more than one document matched the query.  These exceptions are merged into
your document defintions eg: `MyDoc.DoesNotExist`

A variation of this method exists,
:meth:`~mongoengine.queryset.Queryset.get_or_create`, that will create a new
document with the query arguments if no documents match the query. An
additional keyword argument, :attr:`defaults` may be provided, which will be
used as default values for the new document, in the case that it should need
to be created::

    >>> a, created = User.objects.get_or_create(name='User A', defaults={'age': 30})
    >>> b, created = User.objects.get_or_create(name='User A', defaults={'age': 40})
    >>> a.name == b.name and a.age == b.age
    True

Default Document queries
========================
By default, the objects :attr:`~mongoengine.Document.objects` attribute on a
document returns a :class:`~mongoengine.queryset.QuerySet` that doesn't filter
the collection -- it returns all objects. This may be changed by defining a
method on a document that modifies a queryset. The method should accept two
arguments -- :attr:`doc_cls` and :attr:`queryset`. The first argument is the
:class:`~mongoengine.Document` class that the method is defined on (in this
sense, the method is more like a :func:`classmethod` than a regular method),
and the second argument is the initial queryset. The method needs to be
decorated with :func:`~mongoengine.queryset.queryset_manager` in order for it
to be recognised. ::

    class BlogPost(Document):
        title = StringField()
        date = DateTimeField()

        @queryset_manager
        def objects(doc_cls, queryset):
            # This may actually also be done by defining a default ordering for
            # the document, but this illustrates the use of manager methods
            return queryset.order_by('-date')

You don't need to call your method :attr:`objects` -- you may define as many
custom manager methods as you like::

    class BlogPost(Document):
        title = StringField()
        published = BooleanField()

        @queryset_manager
        def live_posts(doc_cls, queryset):
            return queryset.filter(published=True)

    BlogPost(title='test1', published=False).save()
    BlogPost(title='test2', published=True).save()
    assert len(BlogPost.objects) == 2
    assert len(BlogPost.live_posts()) == 1

Custom QuerySets
================
Should you want to add custom methods for interacting with or filtering
documents, extending the :class:`~mongoengine.queryset.QuerySet` class may be
the way to go. To use a custom :class:`~mongoengine.queryset.QuerySet` class on
a document, set ``queryset_class`` to the custom class in a
:class:`~mongoengine.Document`\ s ``meta`` dictionary::

    class AwesomerQuerySet(QuerySet):

        def get_awesome(self):
            return self.filter(awesome=True)

    class Page(Document):
        meta = {'queryset_class': AwesomerQuerySet}

    # To call:
    Page.objects.get_awesome()

.. versionadded:: 0.4

Aggregation
===========
MongoDB provides some aggregation methods out of the box, but there are not as
many as you typically get with an RDBMS. MongoEngine provides a wrapper around
the built-in methods and provides some of its own, which are implemented as
Javascript code that is executed on the database server.

Counting results
----------------
Just as with limiting and skipping results, there is a method on
:class:`~mongoengine.queryset.QuerySet` objects --
:meth:`~mongoengine.queryset.QuerySet.count`, but there is also a more Pythonic
way of achieving this::

    num_users = len(User.objects)

Further aggregation
-------------------
You may sum over the values of a specific field on documents using
:meth:`~mongoengine.queryset.QuerySet.sum`::

    yearly_expense = Employee.objects.sum('salary')

.. note::

   If the field isn't present on a document, that document will be ignored from
   the sum.

To get the average (mean) of a field on a collection of documents, use
:meth:`~mongoengine.queryset.QuerySet.average`::

    mean_age = User.objects.average('age')

Query efficiency and performance
================================

There are a couple of methods to improve efficiency when querying, reducing the
information returned by the query or efficient dereferencing .

Retrieving a subset of fields
-----------------------------

Sometimes a subset of fields on a :class:`~mongoengine.Document` is required,
and for efficiency only these should be retrieved from the database. This issue
is especially important for MongoDB, as fields may often be extremely large
(e.g. a :class:`~mongoengine.fields.ListField` of
:class:`~mongoengine.EmbeddedDocument`\ s, which represent the comments on a
blog post. To select only a subset of fields, use
:meth:`~mongoengine.queryset.QuerySet.only`, specifying the fields you want to
retrieve as its arguments. Note that if fields that are not downloaded are
accessed, their default value (or :attr:`None` if no default value is provided)
will be given::

    >>> class Film(Document):
    ...     title = StringField()
    ...     year = IntField()
    ...     rating = IntField(default=3)
    ...
    >>> Film(title='The Shawshank Redemption', year=1994, rating=5).save()
    >>> f = Film.objects.only('title').first()
    >>> f.title
    'The Shawshank Redemption'
    >>> f.year   # None
    >>> f.rating # default value
    3

.. note::

    The :meth:`~mongoengine.queryset.QuerySet.exclude` is the opposite of
    :meth:`~mongoengine.queryset.QuerySet.only` if you want to exclude a field.

If you later need the missing fields, just call
:meth:`~mongoengine.Document.reload` on your document.

Getting related data
--------------------

When iterating the results of :class:`~mongoengine.fields.ListField` or
:class:`~mongoengine.fields.DictField` we automatically dereference any
:class:`~pymongo.dbref.DBRef` objects as efficiently as possible, reducing the
number the queries to mongo.

There are times when that efficiency is not enough, documents that have
:class:`~mongoengine.fields.ReferenceField` objects or
:class:`~mongoengine.fields.GenericReferenceField` objects at the top level are
expensive as the number of queries to MongoDB can quickly rise.

To limit the number of queries use
:func:`~mongoengine.queryset.QuerySet.select_related` which converts the
QuerySet to a list and dereferences as efficiently as possible.  By default
:func:`~mongoengine.queryset.QuerySet.select_related` only dereferences any
references to the depth of 1 level.  If you have more complicated documents and
want to dereference more of the object at once then increasing the :attr:`max_depth`
will dereference more levels of the document.

Turning off dereferencing
-------------------------

Sometimes for performance reasons you don't want to automatically dereference
data. To turn off dereferencing of the results of a query use
:func:`~mongoengine.queryset.QuerySet.no_dereference` on the queryset like so::

    post = Post.objects.no_dereference().first()
    assert(isinstance(post.author, ObjectId))

You can also turn off all dereferencing for a fixed period by using the
:class:`~mongoengine.context_managers.no_dereference` context manager::

    with no_dereference(Post) as Post:
        post = Post.objects.first()
        assert(isinstance(post.author, ObjectId))

    # Outside the context manager dereferencing occurs.
    assert(isinstance(post.author, User))


Advanced queries
================

Sometimes calling a :class:`~mongoengine.queryset.QuerySet` object with keyword
arguments can't fully express the query you want to use -- for example if you
need to combine a number of constraints using *and* and *or*. This is made
possible in MongoEngine through the :class:`~mongoengine.queryset.Q` class.
A :class:`~mongoengine.queryset.Q` object represents part of a query, and
can be initialised using the same keyword-argument syntax you use to query
documents. To build a complex query, you may combine
:class:`~mongoengine.queryset.Q` objects using the ``&`` (and) and ``|`` (or)
operators. To use a :class:`~mongoengine.queryset.Q` object, pass it in as the
first positional argument to :attr:`Document.objects` when you filter it by
calling it with keyword arguments::

    # Get published posts
    Post.objects(Q(published=True) | Q(publish_date__lte=datetime.now()))

    # Get top posts
    Post.objects((Q(featured=True) & Q(hits__gte=1000)) | Q(hits__gte=5000))

.. warning:: You have to use bitwise operators.  You cannot use ``or``, ``and``
    to combine queries as ``Q(a=a) or Q(b=b)`` is not the same as
    ``Q(a=a) | Q(b=b)``. As ``Q(a=a)`` equates to true ``Q(a=a) or Q(b=b)`` is
    the same as ``Q(a=a)``.

.. _guide-atomic-updates:

Atomic updates
==============
Documents may be updated atomically by using the
:meth:`~mongoengine.queryset.QuerySet.update_one` and
:meth:`~mongoengine.queryset.QuerySet.update` methods on a
:meth:`~mongoengine.queryset.QuerySet`. There are several different "modifiers"
that you may use with these methods:

* ``set`` -- set a particular value
* ``unset`` -- delete a particular value (since MongoDB v1.3+)
* ``inc`` -- increment a value by a given amount
* ``dec`` -- decrement a value by a given amount
* ``pop`` -- remove the last item from a list
* ``push`` -- append a value to a list
* ``pop`` -- remove the first or last element of a list
* ``pull`` -- remove a value from a list
* ``pull_all`` -- remove several values from a list
* ``add_to_set`` -- add value to a list only if its not in the list already

The syntax for atomic updates is similar to the querying syntax, but the
modifier comes before the field, not after it::

    >>> post = BlogPost(title='Test', page_views=0, tags=['database'])
    >>> post.save()
    >>> BlogPost.objects(id=post.id).update_one(inc__page_views=1)
    >>> post.reload()  # the document has been changed, so we need to reload it
    >>> post.page_views
    1
    >>> BlogPost.objects(id=post.id).update_one(set__title='Example Post')
    >>> post.reload()
    >>> post.title
    'Example Post'
    >>> BlogPost.objects(id=post.id).update_one(push__tags='nosql')
    >>> post.reload()
    >>> post.tags
    ['database', 'nosql']

.. note::

    In version 0.5 the :meth:`~mongoengine.Document.save` runs atomic updates
    on changed documents by tracking changes to that document.

The positional operator allows you to update list items without knowing the
index position, therefore making the update a single atomic operation.  As we
cannot use the `$` syntax in keyword arguments it has been mapped to `S`::

    >>> post = BlogPost(title='Test', page_views=0, tags=['database', 'mongo'])
    >>> post.save()
    >>> BlogPost.objects(id=post.id, tags='mongo').update(set__tags__S='mongodb')
    >>> post.reload()
    >>> post.tags
    ['database', 'mongodb']

.. note::
    Currently only top level lists are handled, future versions of mongodb /
    pymongo plan to support nested positional operators.  See `The $ positional
    operator <http://www.mongodb.org/display/DOCS/Updating#Updating-The%24positionaloperator>`_.
