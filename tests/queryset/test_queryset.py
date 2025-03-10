import sys

sys.path[0:0] = [""]

import unittest
import uuid
from datetime import datetime, timedelta

import pymongo
from bson import ObjectId
from nose.plugins.skip import SkipTest
from pymongo.errors import ConfigurationError
from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference

from mongoengine import *
from mongoengine.connection import get_connection
from mongoengine.context_managers import query_counter
from mongoengine.errors import InvalidQueryError
from mongoengine.python_support import PY3
from mongoengine.queryset import (DoesNotExist, MultipleObjectsReturned,
                                  QuerySet, QuerySetManager, queryset_manager)

__all__ = ("QuerySetTest",)


class QuerySetTest(unittest.TestCase):

    def setUp(self):
        connect(db='mongoenginetest')

        class Person(Document):
            name = StringField()
            age = IntField()
            meta = {'allow_inheritance': True}

        Person.drop_collection()
        self.Person = Person

    def test_initialisation(self):
        """Ensure that a QuerySet is correctly initialised by QuerySetManager.
        """
        self.assertTrue(isinstance(self.Person.objects, QuerySet))
        self.assertEqual(self.Person.objects._collection.name,
                         self.Person._get_collection_name())
        self.assertTrue(isinstance(self.Person.objects._collection,
                                   pymongo.collection.Collection))

    def test_cannot_perform_joins_references(self):

        class BlogPost(Document):
            author = ReferenceField(self.Person)
            author2 = GenericReferenceField()

        def test_reference():
            list(BlogPost.objects(author__name="test"))

        self.assertRaises(InvalidQueryError, test_reference)

        def test_generic_reference():
            list(BlogPost.objects(author2__name="test"))

    def test_find(self):
        """Ensure that a query returns a valid set of results.
        """
        self.Person(name="User A", age=20).save()
        self.Person(name="User B", age=30).save()

        # Find all people in the collection
        people = self.Person.objects
        self.assertEqual(people.count(), 2)
        results = list(people)
        self.assertTrue(isinstance(results[0], self.Person))
        self.assertTrue(isinstance(results[0].id, (ObjectId, str)))
        self.assertEqual(results[0].name, "User A")
        self.assertEqual(results[0].age, 20)
        self.assertEqual(results[1].name, "User B")
        self.assertEqual(results[1].age, 30)

        # Use a query to filter the people found to just person1
        people = self.Person.objects(age=20)
        self.assertEqual(people.count(), 1)
        person = next(people)
        self.assertEqual(person.name, "User A")
        self.assertEqual(person.age, 20)

        # Test limit
        people = list(self.Person.objects.limit(1))
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].name, 'User A')

        # Test skip
        people = list(self.Person.objects.skip(1))
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].name, 'User B')

        person3 = self.Person(name="User C", age=40)
        person3.save()

        # Test slice limit
        people = list(self.Person.objects[:2])
        self.assertEqual(len(people), 2)
        self.assertEqual(people[0].name, 'User A')
        self.assertEqual(people[1].name, 'User B')

        # Test slice skip
        people = list(self.Person.objects[1:])
        self.assertEqual(len(people), 2)
        self.assertEqual(people[0].name, 'User B')
        self.assertEqual(people[1].name, 'User C')

        # Test slice limit and skip
        people = list(self.Person.objects[1:2])
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].name, 'User B')

        # Test slice limit and skip cursor reset
        qs = self.Person.objects[1:2]
        # fetch then delete the cursor
        qs._cursor
        qs._cursor_obj = None
        people = list(qs)
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].name, 'User B')

        people = list(self.Person.objects[1:1])
        self.assertEqual(len(people), 0)

        # Test slice out of range
        people = list(self.Person.objects[80000:80001])
        self.assertEqual(len(people), 0)

        # Test larger slice __repr__
        self.Person.objects.delete()
        for i in range(55):
            self.Person(name='A%s' % i, age=i).save()

        self.assertEqual(self.Person.objects.count(), 55)
        self.assertEqual("Person object", "%s" % self.Person.objects[0])
        self.assertEqual("[<Person: Person object>, <Person: Person object>]",  "%s" % self.Person.objects[1:3])
        self.assertEqual("[<Person: Person object>, <Person: Person object>]",  "%s" % self.Person.objects[51:53])

    def test_find_one(self):
        """Ensure that a query using find_one returns a valid result.
        """
        person1 = self.Person(name="User A", age=20)
        person1.save()
        person2 = self.Person(name="User B", age=30)
        person2.save()

        # Retrieve the first person from the database
        person = self.Person.objects.first()
        self.assertTrue(isinstance(person, self.Person))
        self.assertEqual(person.name, "User A")
        self.assertEqual(person.age, 20)

        # Use a query to filter the people found to just person2
        person = self.Person.objects(age=30).first()
        self.assertEqual(person.name, "User B")

        person = self.Person.objects(age__lt=30).first()
        self.assertEqual(person.name, "User A")

        # Use array syntax
        person = self.Person.objects[0]
        self.assertEqual(person.name, "User A")

        person = self.Person.objects[1]
        self.assertEqual(person.name, "User B")

        self.assertRaises(IndexError, self.Person.objects.__getitem__, 2)

        # Find a document using just the object id
        person = self.Person.objects.with_id(person1.id)
        self.assertEqual(person.name, "User A")

        self.assertRaises(InvalidQueryError, self.Person.objects(name="User A").with_id, person1.id)

    def test_find_only_one(self):
        """Ensure that a query using ``get`` returns at most one result.
        """
        # Try retrieving when no objects exists
        self.assertRaises(DoesNotExist, self.Person.objects.get)
        self.assertRaises(self.Person.DoesNotExist, self.Person.objects.get)

        person1 = self.Person(name="User A", age=20)
        person1.save()
        person2 = self.Person(name="User B", age=30)
        person2.save()

        # Retrieve the first person from the database
        self.assertRaises(MultipleObjectsReturned, self.Person.objects.get)
        self.assertRaises(self.Person.MultipleObjectsReturned,
                          self.Person.objects.get)

        # Use a query to filter the people found to just person2
        person = self.Person.objects.get(age=30)
        self.assertEqual(person.name, "User B")

        person = self.Person.objects.get(age__lt=30)
        self.assertEqual(person.name, "User A")

    def test_find_array_position(self):
        """Ensure that query by array position works.
        """
        class Comment(EmbeddedDocument):
            name = StringField()

        class Post(EmbeddedDocument):
            comments = ListField(EmbeddedDocumentField(Comment))

        class Blog(Document):
            tags = ListField(StringField())
            posts = ListField(EmbeddedDocumentField(Post))

        Blog.drop_collection()

        Blog.objects.create(tags=['a', 'b'])
        self.assertEqual(Blog.objects(tags__0='a').count(), 1)
        self.assertEqual(Blog.objects(tags__0='b').count(), 0)
        self.assertEqual(Blog.objects(tags__1='a').count(), 0)
        self.assertEqual(Blog.objects(tags__1='b').count(), 1)

        Blog.drop_collection()

        comment1 = Comment(name='testa')
        comment2 = Comment(name='testb')
        post1 = Post(comments=[comment1, comment2])
        post2 = Post(comments=[comment2, comment2])
        blog1 = Blog.objects.create(posts=[post1, post2])
        blog2 = Blog.objects.create(posts=[post2, post1])

        blog = Blog.objects(posts__0__comments__0__name='testa').get()
        self.assertEqual(blog, blog1)

        query = Blog.objects(posts__1__comments__1__name='testb')
        self.assertEqual(query.count(), 2)

        query = Blog.objects(posts__1__comments__1__name='testa')
        self.assertEqual(query.count(), 0)

        query = Blog.objects(posts__0__comments__1__name='testa')
        self.assertEqual(query.count(), 0)

        Blog.drop_collection()

    def test_none(self):
        class A(Document):
            s = StringField()

        A.drop_collection()
        A().save()

        self.assertEqual(list(A.objects.none()), [])
        self.assertEqual(list(A.objects.none().all()), [])
        self.assertEqual(A.objects.none().count(), 0)

    def test_chaining(self):
        class A(Document):
            s = StringField()

        class B(Document):
            ref = ReferenceField(A)
            boolfield = BooleanField(default=False)

        A.drop_collection()
        B.drop_collection()

        a1 = A(s="test1").save()
        a2 = A(s="test2").save()

        B(ref=a1, boolfield=True).save()

        # Works
        q1 = B.objects.filter(ref__in=[a1, a2], ref=a1)._query

        # Doesn't work
        q2 = B.objects.filter(ref__in=[a1, a2])
        q2 = q2.filter(ref=a1)._query
        self.assertEqual(q1, q2)

        a_objects = A.objects(s='test1')
        query = B.objects(ref__in=a_objects)
        query = query.filter(boolfield=True)
        self.assertEqual(query.count(), 1)

    def test_batch_size(self):
        """Test that batch_size works."""
        class A(Document):
            s = StringField()

        A.drop_collection()

        for i in range(100):
            A.objects.create(s=str(i))

        cnt = 0
        for a in A.objects.batch_size(10):
            cnt += 1

        self.assertEqual(cnt, 100)

        # test chaining
        qs = A.objects.all()
        qs = qs.limit(10).batch_size(20).skip(91)
        cnt = 0
        for a in qs:
            cnt += 1

        self.assertEqual(cnt, 9)

    def test_update_write_concern(self):
        """Test that passing write_concern works"""

        self.Person.drop_collection()

        write_concern = {"fsync": True}

        author, created = self.Person.objects.get_or_create(
            name='Test User', write_concern=write_concern)
        author.save(write_concern=write_concern)

        result = self.Person.objects.update(
            set__name='Ross', write_concern={"w": 1})
        self.assertEqual(result, 1)
        result = self.Person.objects.update(
            set__name='Ross', write_concern={"w": 0})
        self.assertEqual(result, None)

        result = self.Person.objects.update_one(
            set__name='Test User', write_concern={"w": 1})
        self.assertEqual(result, 1)
        result = self.Person.objects.update_one(
            set__name='Test User', write_concern={"w": 0})
        self.assertEqual(result, None)

    def test_update_update_has_a_value(self):
        """Test to ensure that update is passed a value to update to"""
        self.Person.drop_collection()

        author = self.Person(name='Test User')
        author.save()

        def update_raises():
            self.Person.objects(pk=author.pk).update({})

        def update_one_raises():
            self.Person.objects(pk=author.pk).update_one({})

        self.assertRaises(OperationError, update_raises)
        self.assertRaises(OperationError, update_one_raises)

    def test_update_array_position(self):
        """Ensure that updating by array position works.

        Check update() and update_one() can take syntax like:
            set__posts__1__comments__1__name="testc"
        Check that it only works for ListFields.
        """
        class Comment(EmbeddedDocument):
            name = StringField()

        class Post(EmbeddedDocument):
            comments = ListField(EmbeddedDocumentField(Comment))

        class Blog(Document):
            tags = ListField(StringField())
            posts = ListField(EmbeddedDocumentField(Post))

        Blog.drop_collection()

        comment1 = Comment(name='testa')
        comment2 = Comment(name='testb')
        post1 = Post(comments=[comment1, comment2])
        post2 = Post(comments=[comment2, comment2])
        Blog.objects.create(posts=[post1, post2])
        Blog.objects.create(posts=[post2, post1])

        # Update all of the first comments of second posts of all blogs
        Blog.objects().update(set__posts__1__comments__0__name="testc")
        testc_blogs = Blog.objects(posts__1__comments__0__name="testc")
        self.assertEqual(testc_blogs.count(), 2)

        Blog.drop_collection()
        Blog.objects.create(posts=[post1, post2])
        Blog.objects.create(posts=[post2, post1])

        # Update only the first blog returned by the query
        Blog.objects().update_one(
            set__posts__1__comments__1__name="testc")
        testc_blogs = Blog.objects(posts__1__comments__1__name="testc")
        self.assertEqual(testc_blogs.count(), 1)

        # Check that using this indexing syntax on a non-list fails
        def non_list_indexing():
            Blog.objects().update(set__posts__1__comments__0__name__1="asdf")
        self.assertRaises(InvalidQueryError, non_list_indexing)

        Blog.drop_collection()

    def test_update_using_positional_operator(self):
        """Ensure that the list fields can be updated using the positional
        operator."""

        class Comment(EmbeddedDocument):
            by = StringField()
            votes = IntField()

        class BlogPost(Document):
            title = StringField()
            comments = ListField(EmbeddedDocumentField(Comment))

        BlogPost.drop_collection()

        c1 = Comment(by="joe", votes=3)
        c2 = Comment(by="jane", votes=7)

        BlogPost(title="ABC", comments=[c1, c2]).save()

        BlogPost.objects(comments__by="jane").update(inc__comments__S__votes=1)

        post = BlogPost.objects.first()
        self.assertEqual(post.comments[1].by, 'jane')
        self.assertEqual(post.comments[1].votes, 8)

    def test_update_using_positional_operator_matches_first(self):

        # Currently the $ operator only applies to the first matched item in
        # the query

        class Simple(Document):
            x = ListField()

        Simple.drop_collection()
        Simple(x=[1, 2, 3, 2]).save()
        Simple.objects(x=2).update(inc__x__S=1)

        simple = Simple.objects.first()
        self.assertEqual(simple.x, [1, 3, 3, 2])
        Simple.drop_collection()

        # You can set multiples
        Simple.drop_collection()
        Simple(x=[1, 2, 3, 4]).save()
        Simple(x=[2, 3, 4, 5]).save()
        Simple(x=[3, 4, 5, 6]).save()
        Simple(x=[4, 5, 6, 7]).save()
        Simple.objects(x=3).update(set__x__S=0)

        s = Simple.objects()
        self.assertEqual(s[0].x, [1, 2, 0, 4])
        self.assertEqual(s[1].x, [2, 0, 4, 5])
        self.assertEqual(s[2].x, [0, 4, 5, 6])
        self.assertEqual(s[3].x, [4, 5, 6, 7])

        # Using "$unset" with an expression like this "array.$" will result in
        # the array item becoming None, not being removed.
        Simple.drop_collection()
        Simple(x=[1, 2, 3, 4, 3, 2, 3, 4]).save()
        Simple.objects(x=3).update(unset__x__S=1)
        simple = Simple.objects.first()
        self.assertEqual(simple.x, [1, 2, None, 4, 3, 2, 3, 4])

        # Nested updates arent supported yet..
        def update_nested():
            Simple.drop_collection()
            Simple(x=[{'test': [1, 2, 3, 4]}]).save()
            Simple.objects(x__test=2).update(set__x__S__test__S=3)
            self.assertEqual(simple.x, [1, 2, 3, 4])

        self.assertRaises(OperationError, update_nested)
        Simple.drop_collection()

    def test_update_using_positional_operator_embedded_document(self):
        """Ensure that the embedded documents can be updated using the positional
        operator."""

        class Vote(EmbeddedDocument):
            score = IntField()

        class Comment(EmbeddedDocument):
            by = StringField()
            votes = EmbeddedDocumentField(Vote)

        class BlogPost(Document):
            title = StringField()
            comments = ListField(EmbeddedDocumentField(Comment))

        BlogPost.drop_collection()

        c1 = Comment(by="joe", votes=Vote(score=3))
        c2 = Comment(by="jane", votes=Vote(score=7))

        BlogPost(title="ABC", comments=[c1, c2]).save()

        BlogPost.objects(comments__by="joe").update(set__comments__S__votes=Vote(score=4))

        post = BlogPost.objects.first()
        self.assertEqual(post.comments[0].by, 'joe')
        self.assertEqual(post.comments[0].votes.score, 4)

    def test_updates_can_have_match_operators(self):

        class Post(Document):
            title = StringField(required=True)
            tags = ListField(StringField())
            comments = ListField(EmbeddedDocumentField("Comment"))

        class Comment(EmbeddedDocument):
            content = StringField()
            name = StringField(max_length=120)
            vote = IntField()

        Post.drop_collection()

        comm1 = Comment(content="very funny indeed", name="John S", vote=1)
        comm2 = Comment(content="kind of funny", name="Mark P", vote=0)

        Post(title='Fun with MongoEngine', tags=['mongodb', 'mongoengine'],
             comments=[comm1, comm2]).save()

        Post.objects().update_one(pull__comments__vote__lt=1)

        self.assertEqual(1, len(Post.objects.first().comments))

    def test_mapfield_update(self):
        """Ensure that the MapField can be updated."""
        class Member(EmbeddedDocument):
            gender = StringField()
            age = IntField()

        class Club(Document):
            members = MapField(EmbeddedDocumentField(Member))

        Club.drop_collection()

        club = Club()
        club.members['John'] = Member(gender="M", age=13)
        club.save()

        Club.objects().update(
            set__members={"John": Member(gender="F", age=14)})

        club = Club.objects().first()
        self.assertEqual(club.members['John'].gender, "F")
        self.assertEqual(club.members['John'].age, 14)

    def test_dictfield_update(self):
        """Ensure that the DictField can be updated."""
        class Club(Document):
            members = DictField()

        club = Club()
        club.members['John'] = dict(gender="M", age=13)
        club.save()

        Club.objects().update(
            set__members={"John": dict(gender="F", age=14)})

        club = Club.objects().first()
        self.assertEqual(club.members['John']['gender'], "F")
        self.assertEqual(club.members['John']['age'], 14)

    def test_upsert(self):
        self.Person.drop_collection()

        self.Person.objects(pk=ObjectId(), name="Bob", age=30).update(upsert=True)

        bob = self.Person.objects.first()
        self.assertEqual("Bob", bob.name)
        self.assertEqual(30, bob.age)

    def test_upsert_one(self):
        self.Person.drop_collection()

        self.Person.objects(name="Bob", age=30).update_one(upsert=True)

        bob = self.Person.objects.first()
        self.assertEqual("Bob", bob.name)
        self.assertEqual(30, bob.age)

    def test_set_on_insert(self):
        self.Person.drop_collection()

        self.Person.objects(pk=ObjectId()).update(set__name='Bob', set_on_insert__age=30, upsert=True)

        bob = self.Person.objects.first()
        self.assertEqual("Bob", bob.name)
        self.assertEqual(30, bob.age)

    def test_get_or_create(self):
        """Ensure that ``get_or_create`` returns one result or creates a new
        document.
        """
        person1 = self.Person(name="User A", age=20)
        person1.save()
        person2 = self.Person(name="User B", age=30)
        person2.save()

        # Retrieve the first person from the database
        self.assertRaises(MultipleObjectsReturned,
                          self.Person.objects.get_or_create)
        self.assertRaises(self.Person.MultipleObjectsReturned,
                          self.Person.objects.get_or_create)

        # Use a query to filter the people found to just person2
        person, created = self.Person.objects.get_or_create(age=30)
        self.assertEqual(person.name, "User B")
        self.assertEqual(created, False)

        person, created = self.Person.objects.get_or_create(age__lt=30)
        self.assertEqual(person.name, "User A")
        self.assertEqual(created, False)

        # Try retrieving when no objects exists - new doc should be created
        kwargs = dict(age=50, defaults={'name': 'User C'})
        person, created = self.Person.objects.get_or_create(**kwargs)
        self.assertEqual(created, True)

        person = self.Person.objects.get(age=50)
        self.assertEqual(person.name, "User C")

    def test_bulk_insert(self):
        """Ensure that bulk insert works
        """
        class Comment(EmbeddedDocument):
            name = StringField()

        class Post(EmbeddedDocument):
            comments = ListField(EmbeddedDocumentField(Comment))

        class Blog(Document):
            title = StringField(unique=True)
            tags = ListField(StringField())
            posts = ListField(EmbeddedDocumentField(Post))

        Blog.drop_collection()

        # Recreates the collection
        self.assertEqual(0, Blog.objects.count())

        comment1 = Comment(name='testa')
        comment2 = Comment(name='testb')
        post1 = Post(comments=[comment1, comment2])
        post2 = Post(comments=[comment2, comment2])

        # Check bulk insert using load_bulk=False
        blogs = [Blog(title="%s" % i, posts=[post1, post2])
                 for i in range(99)]
        with query_counter() as q:
            self.assertEqual(q, 0)
            Blog.objects.insert(blogs, load_bulk=False)
            self.assertEqual(q, 1)  # 1 entry containing the list of inserts

        self.assertEqual(Blog.objects.count(), len(blogs))

        Blog.drop_collection()
        Blog.ensure_indexes()

        # Check bulk insert using load_bulk=True
        blogs = [Blog(title="%s" % i, posts=[post1, post2])
                 for i in range(99)]
        with query_counter() as q:
            self.assertEqual(q, 0)
            Blog.objects.insert(blogs)
            self.assertEqual(q, 2)  # 1 for insert 1 for fetch

        Blog.drop_collection()

        comment1 = Comment(name='testa')
        comment2 = Comment(name='testb')
        post1 = Post(comments=[comment1, comment2])
        post2 = Post(comments=[comment2, comment2])
        blog1 = Blog(title="code", posts=[post1, post2])
        blog2 = Blog(title="mongodb", posts=[post2, post1])
        blog1, blog2 = Blog.objects.insert([blog1, blog2])
        self.assertEqual(blog1.title, "code")
        self.assertEqual(blog2.title, "mongodb")

        self.assertEqual(Blog.objects.count(), 2)

        # test inserting an existing document (shouldn't be allowed)
        with self.assertRaises(OperationError) as cm:
            blog = Blog.objects.first()
            Blog.objects.insert(blog)
        self.assertEqual(
            str(cm.exception),
            'Some documents have ObjectIds, use doc.update() instead'
        )

        # test inserting a query set
        with self.assertRaises(OperationError) as cm:
            blogs_qs = Blog.objects
            Blog.objects.insert(blogs_qs)
        self.assertEqual(
            str(cm.exception),
            'Some documents have ObjectIds, use doc.update() instead'
        )

        # insert 1 new doc
        new_post = Blog(title="code123", id=ObjectId())
        Blog.objects.insert(new_post)

        Blog.drop_collection()

        blog1 = Blog(title="code", posts=[post1, post2])
        blog1 = Blog.objects.insert(blog1)
        self.assertEqual(blog1.title, "code")
        self.assertEqual(Blog.objects.count(), 1)

        Blog.drop_collection()
        blog1 = Blog(title="code", posts=[post1, post2])
        obj_id = Blog.objects.insert(blog1, load_bulk=False)
        self.assertIsInstance(obj_id, ObjectId)

        Blog.drop_collection()
        Blog.ensure_indexes()
        post3 = Post(comments=[comment1, comment1])
        blog1 = Blog(title="foo", posts=[post1, post2])
        blog2 = Blog(title="bar", posts=[post2, post3])
        Blog.objects.insert([blog1, blog2])

        with self.assertRaises(NotUniqueError):
            Blog.objects.insert(Blog(title=blog2.title))

        self.assertEqual(Blog.objects.count(), 2)

    def test_get_changed_fields_query_count(self):

        class Person(Document):
            name = StringField()
            owns = ListField(ReferenceField('Organization'))
            projects = ListField(ReferenceField('Project'))

        class Organization(Document):
            name = StringField()
            owner = ReferenceField('Person')
            employees = ListField(ReferenceField('Person'))

        class Project(Document):
            name = StringField()

        Person.drop_collection()
        Organization.drop_collection()
        Project.drop_collection()

        r1 = Project(name="r1").save()
        r2 = Project(name="r2").save()
        r3 = Project(name="r3").save()
        p1 = Person(name="p1", projects=[r1, r2]).save()
        p2 = Person(name="p2", projects=[r2, r3]).save()
        o1 = Organization(name="o1", employees=[p1]).save()

        with query_counter() as q:
            self.assertEqual(q, 0)

            fresh_o1 = Organization.objects.get(id=o1.id)
            self.assertEqual(1, q)
            fresh_o1._get_changed_fields()
            self.assertEqual(1, q)

        with query_counter() as q:
            self.assertEqual(q, 0)

            fresh_o1 = Organization.objects.get(id=o1.id)
            fresh_o1.save()   # No changes, does nothing

            self.assertEqual(q, 1)

        with query_counter() as q:
            self.assertEqual(q, 0)

            fresh_o1 = Organization.objects.get(id=o1.id)
            fresh_o1.save(cascade=False)  # No changes, does nothing

            self.assertEqual(q, 1)

        with query_counter() as q:
            self.assertEqual(q, 0)

            fresh_o1 = Organization.objects.get(id=o1.id)
            fresh_o1.employees.append(p2)
            fresh_o1.save(cascade=False)   # Saves

            self.assertEqual(q, 2)

    def test_timeout_and_cursor_args(self):
        """Ensures the cursor args can be set as expected
        """
        p = self.Person.objects
        self.assertEqual(p._cursor_args, {})

        p = p.timeout(True)
        self.assertEqual(p._cursor_args, {})

        p = p.timeout(False)
        self.assertEqual(p._cursor_args, {'no_cursor_timeout': True})

    def test_repeated_iteration(self):
        """Ensure that QuerySet rewinds itself one iteration finishes.
        """
        self.Person(name='Person 1').save()
        self.Person(name='Person 2').save()

        queryset = self.Person.objects
        people1 = [person for person in queryset]
        people2 = [person for person in queryset]

        # Check that it still works even if iteration is interrupted.
        for person in queryset:
            break
        people3 = [person for person in queryset]

        self.assertEqual(people1, people2)
        self.assertEqual(people1, people3)

    def test_repr(self):
        """Test repr behavior isnt destructive"""

        class Doc(Document):
            number = IntField()

            def __repr__(self):
                return "<Doc: %s>" % self.number

        Doc.drop_collection()

        for i in range(1000):
            Doc(number=i).save()

        docs = Doc.objects.order_by('number')

        self.assertEqual(docs.count(), 1000)

        docs_string = "%s" % docs
        self.assertTrue("Doc: 0" in docs_string)

        self.assertEqual(docs.count(), 1000)
        self.assertTrue('(remaining elements truncated)' in "%s" % docs)

        # Limit and skip
        docs = docs[1:4]
        self.assertEqual('[<Doc: 1>, <Doc: 2>, <Doc: 3>]', "%s" % docs)

        self.assertEqual(docs.count(), 3)
        for doc in docs:
            self.assertEqual('.. queryset mid-iteration ..', repr(docs))

    def test_regex_query_shortcuts(self):
        """Ensure that contains, startswith, endswith, etc work.
        """
        person = self.Person(name='Guido van Rossum')
        person.save()

        # Test contains
        obj = self.Person.objects(name__contains='van').first()
        self.assertEqual(obj, person)
        obj = self.Person.objects(name__contains='Van').first()
        self.assertEqual(obj, None)

        # Test icontains
        obj = self.Person.objects(name__icontains='Van').first()
        self.assertEqual(obj, person)

        # Test startswith
        obj = self.Person.objects(name__startswith='Guido').first()
        self.assertEqual(obj, person)
        obj = self.Person.objects(name__startswith='guido').first()
        self.assertEqual(obj, None)

        # Test istartswith
        obj = self.Person.objects(name__istartswith='guido').first()
        self.assertEqual(obj, person)

        # Test endswith
        obj = self.Person.objects(name__endswith='Rossum').first()
        self.assertEqual(obj, person)
        obj = self.Person.objects(name__endswith='rossuM').first()
        self.assertEqual(obj, None)

        # Test iendswith
        obj = self.Person.objects(name__iendswith='rossuM').first()
        self.assertEqual(obj, person)

        # Test exact
        obj = self.Person.objects(name__exact='Guido van Rossum').first()
        self.assertEqual(obj, person)
        obj = self.Person.objects(name__exact='Guido van rossum').first()
        self.assertEqual(obj, None)
        obj = self.Person.objects(name__exact='Guido van Rossu').first()
        self.assertEqual(obj, None)

        # Test iexact
        obj = self.Person.objects(name__iexact='gUIDO VAN rOSSUM').first()
        self.assertEqual(obj, person)
        obj = self.Person.objects(name__iexact='gUIDO VAN rOSSU').first()
        self.assertEqual(obj, None)

        # Test unsafe expressions
        person = self.Person(name='Guido van Rossum [.\'Geek\']')
        person.save()

        obj = self.Person.objects(name__icontains='[.\'Geek').first()
        self.assertEqual(obj, person)

    def test_not(self):
        """Ensure that the __not operator works as expected.
        """
        alice = self.Person(name='Alice', age=25)
        alice.save()

        obj = self.Person.objects(name__iexact='alice').first()
        self.assertEqual(obj, alice)

        obj = self.Person.objects(name__not__iexact='alice').first()
        self.assertEqual(obj, None)

    def test_filter_chaining(self):
        """Ensure filters can be chained together.
        """
        class Blog(Document):
            id = StringField(unique=True, primary_key=True)

        class BlogPost(Document):
            blog = ReferenceField(Blog)
            title = StringField()
            is_published = BooleanField()
            published_date = DateTimeField()

            @queryset_manager
            def published(doc_cls, queryset):
                return queryset(is_published=True)

        Blog.drop_collection()
        BlogPost.drop_collection()

        blog_1 = Blog(id="1")
        blog_2 = Blog(id="2")
        blog_3 = Blog(id="3")

        blog_1.save()
        blog_2.save()
        blog_3.save()

        blog_post_1 = BlogPost(blog=blog_1, title="Blog Post #1",
                               is_published=True,
                               published_date=datetime(2010, 1, 5, 0, 0, 0))
        blog_post_2 = BlogPost(blog=blog_2, title="Blog Post #2",
                               is_published=True,
                               published_date=datetime(2010, 1, 6, 0, 0, 0))
        blog_post_3 = BlogPost(blog=blog_3, title="Blog Post #3",
                               is_published=True,
                               published_date=datetime(2010, 1, 7, 0, 0, 0))

        blog_post_1.save()
        blog_post_2.save()
        blog_post_3.save()

        # find all published blog posts before 2010-01-07
        published_posts = BlogPost.published()
        published_posts = published_posts.filter(
            published_date__lt=datetime(2010, 1, 7, 0, 0, 0))
        self.assertEqual(published_posts.count(), 2)

        blog_posts = BlogPost.objects
        blog_posts = blog_posts.filter(blog__in=[blog_1, blog_2])
        blog_posts = blog_posts.filter(blog=blog_3)
        self.assertEqual(blog_posts.count(), 0)

        BlogPost.drop_collection()
        Blog.drop_collection()

    def assertSequence(self, qs, expected):
        qs = list(qs)
        expected = list(expected)
        self.assertEqual(len(qs), len(expected))
        for i in range(len(qs)):
            self.assertEqual(qs[i], expected[i])

    def test_ordering(self):
        """Ensure default ordering is applied and can be overridden.
        """
        class BlogPost(Document):
            title = StringField()
            published_date = DateTimeField()

            meta = {
                'ordering': ['-published_date']
            }

        BlogPost.drop_collection()

        blog_post_1 = BlogPost(title="Blog Post #1",
                               published_date=datetime(2010, 1, 5, 0, 0, 0))
        blog_post_2 = BlogPost(title="Blog Post #2",
                               published_date=datetime(2010, 1, 6, 0, 0, 0))
        blog_post_3 = BlogPost(title="Blog Post #3",
                               published_date=datetime(2010, 1, 7, 0, 0, 0))

        blog_post_1.save()
        blog_post_2.save()
        blog_post_3.save()

        # get the "first" BlogPost using default ordering
        # from BlogPost.meta.ordering
        expected = [blog_post_3, blog_post_2, blog_post_1]
        self.assertSequence(BlogPost.objects.all(), expected)

        # override default ordering, order BlogPosts by "published_date"
        qs = BlogPost.objects.order_by("+published_date")
        expected = [blog_post_1, blog_post_2, blog_post_3]
        self.assertSequence(qs, expected)

    def test_find_embedded(self):
        """Ensure that an embedded document is properly returned from a query.
        """
        class User(EmbeddedDocument):
            name = StringField()

        class BlogPost(Document):
            content = StringField()
            author = EmbeddedDocumentField(User)

        BlogPost.drop_collection()

        post = BlogPost(content='Had a good coffee today...')
        post.author = User(name='Test User')
        post.save()

        result = BlogPost.objects.first()
        self.assertTrue(isinstance(result.author, User))
        self.assertEqual(result.author.name, 'Test User')

        BlogPost.drop_collection()

    def test_find_dict_item(self):
        """Ensure that DictField items may be found.
        """
        class BlogPost(Document):
            info = DictField()

        BlogPost.drop_collection()

        post = BlogPost(info={'title': 'test'})
        post.save()

        post_obj = BlogPost.objects(info__title='test').first()
        self.assertEqual(post_obj.id, post.id)

        BlogPost.drop_collection()

    def test_delete(self):
        """Ensure that documents are properly deleted from the database.
        """
        self.Person(name="User A", age=20).save()
        self.Person(name="User B", age=30).save()
        self.Person(name="User C", age=40).save()

        self.assertEqual(self.Person.objects.count(), 3)

        self.Person.objects(age__lt=30).delete()
        self.assertEqual(self.Person.objects.count(), 2)

        self.Person.objects.delete()
        self.assertEqual(self.Person.objects.count(), 0)

    def test_reverse_delete_rule_cascade(self):
        """Ensure cascading deletion of referring documents from the database.
        """
        class BlogPost(Document):
            content = StringField()
            author = ReferenceField(self.Person, reverse_delete_rule=CASCADE)
        BlogPost.drop_collection()

        me = self.Person(name='Test User')
        me.save()
        someoneelse = self.Person(name='Some-one Else')
        someoneelse.save()

        BlogPost(content='Watching TV', author=me).save()
        BlogPost(content='Chilling out', author=me).save()
        BlogPost(content='Pro Testing', author=someoneelse).save()

        self.assertEqual(3, BlogPost.objects.count())
        self.Person.objects(name='Test User').delete()
        self.assertEqual(1, BlogPost.objects.count())

    def test_reverse_delete_rule_cascade_self_referencing(self):
        """Ensure self-referencing CASCADE deletes do not result in infinite
        loop
        """
        class Category(Document):
            name = StringField()
            parent = ReferenceField('self', reverse_delete_rule=CASCADE)

        Category.drop_collection()

        num_children = 3
        base = Category(name='Root')
        base.save()

        # Create a simple parent-child tree
        for i in range(num_children):
            child_name = 'Child-%i' % i
            child = Category(name=child_name, parent=base)
            child.save()

            for i in range(num_children):
                child_child_name = 'Child-Child-%i' % i
                child_child = Category(name=child_child_name, parent=child)
                child_child.save()

        tree_size = 1 + num_children + (num_children * num_children)
        self.assertEqual(tree_size, Category.objects.count())
        self.assertEqual(num_children, Category.objects(parent=base).count())

        # The delete should effectively wipe out the Category collection
        # without resulting in infinite parent-child cascade recursion
        base.delete()
        self.assertEqual(0, Category.objects.count())

    def test_reverse_delete_rule_nullify(self):
        """Ensure nullification of references to deleted documents.
        """
        class Category(Document):
            name = StringField()

        class BlogPost(Document):
            content = StringField()
            category = ReferenceField(Category, reverse_delete_rule=NULLIFY)

        BlogPost.drop_collection()
        Category.drop_collection()

        lameness = Category(name='Lameness')
        lameness.save()

        post = BlogPost(content='Watching TV', category=lameness)
        post.save()

        self.assertEqual(1, BlogPost.objects.count())
        self.assertEqual('Lameness', BlogPost.objects.first().category.name)
        Category.objects.delete()
        self.assertEqual(1, BlogPost.objects.count())
        self.assertEqual(None, BlogPost.objects.first().category)

    def test_reverse_delete_rule_deny(self):
        """Ensure deletion gets denied on documents that still have references
        to them.
        """
        class BlogPost(Document):
            content = StringField()
            author = ReferenceField(self.Person, reverse_delete_rule=DENY)

        BlogPost.drop_collection()
        self.Person.drop_collection()

        me = self.Person(name='Test User')
        me.save()

        post = BlogPost(content='Watching TV', author=me)
        post.save()

        self.assertRaises(OperationError, self.Person.objects.delete)

    def test_reverse_delete_rule_pull(self):
        """Ensure pulling of references to deleted documents.
        """
        class BlogPost(Document):
            content = StringField()
            authors = ListField(ReferenceField(self.Person,
                                reverse_delete_rule=PULL))

        BlogPost.drop_collection()
        self.Person.drop_collection()

        me = self.Person(name='Test User')
        me.save()

        someoneelse = self.Person(name='Some-one Else')
        someoneelse.save()

        post = BlogPost(content='Watching TV', authors=[me, someoneelse])
        post.save()

        another = BlogPost(content='Chilling Out', authors=[someoneelse])
        another.save()

        someoneelse.delete()
        post.reload()
        another.reload()

        self.assertEqual(post.authors, [me])
        self.assertEqual(another.authors, [])

    def test_delete_with_limits(self):

        class Log(Document):
            pass

        Log.drop_collection()

        for i in range(10):
            Log().save()

        Log.objects()[3:5].delete()
        self.assertEqual(8, Log.objects.count())

    def test_delete_with_limit_handles_delete_rules(self):
        """Ensure cascading deletion of referring documents from the database.
        """
        class BlogPost(Document):
            content = StringField()
            author = ReferenceField(self.Person, reverse_delete_rule=CASCADE)
        BlogPost.drop_collection()

        me = self.Person(name='Test User')
        me.save()
        someoneelse = self.Person(name='Some-one Else')
        someoneelse.save()

        BlogPost(content='Watching TV', author=me).save()
        BlogPost(content='Chilling out', author=me).save()
        BlogPost(content='Pro Testing', author=someoneelse).save()

        self.assertEqual(3, BlogPost.objects.count())
        self.Person.objects()[:1].delete()
        self.assertEqual(1, BlogPost.objects.count())

    def test_reference_field_find(self):
        """Ensure cascading deletion of referring documents from the database.
        """
        # Needed to test a regression where extra queries are made
        # when polymorphic `ReferenceField`s are queried by pk (and not object)
        assert self.Person._meta["allow_inheritance"]

        class BlogPost(Document):
            content = StringField()
            author = ReferenceField(self.Person)

        BlogPost.drop_collection()
        self.Person.drop_collection()

        me = self.Person(name='Test User').save()
        BlogPost(content="test 123", author=me).save()

        with query_counter() as q:
            self.assertEqual(1, BlogPost.objects(author=me).count())
            self.assertEqual(1, BlogPost.objects(author=me.pk).count())
            self.assertEqual(1, BlogPost.objects(author="%s" % me.pk).count())

            self.assertEqual(1, BlogPost.objects(author__in=[me]).count())
            self.assertEqual(1, BlogPost.objects(author__in=[me.pk]).count())
            self.assertEqual(1, BlogPost.objects(author__in=["%s" % me.pk]).count())

            self.assertEqual(q, 6)

    def test_reference_field_find_dbref(self):
        """Ensure cascading deletion of referring documents from the database.
        """
        class BlogPost(Document):
            content = StringField()
            author = ReferenceField(self.Person, dbref=True)

        BlogPost.drop_collection()
        self.Person.drop_collection()

        me = self.Person(name='Test User').save()
        BlogPost(content="test 123", author=me).save()

        self.assertEqual(1, BlogPost.objects(author=me).count())
        self.assertEqual(1, BlogPost.objects(author=me.pk).count())
        self.assertEqual(1, BlogPost.objects(author="%s" % me.pk).count())

        self.assertEqual(1, BlogPost.objects(author__in=[me]).count())
        self.assertEqual(1, BlogPost.objects(author__in=[me.pk]).count())
        self.assertEqual(1, BlogPost.objects(author__in=["%s" % me.pk]).count())

    def test_update(self):
        """Ensure that atomic updates work properly.
        """
        class BlogPost(Document):
            title = StringField()
            hits = IntField()
            tags = ListField(StringField())

        BlogPost.drop_collection()

        post = BlogPost(title="Test Post", hits=5, tags=['test'])
        post.save()

        BlogPost.objects.update(set__hits=10)
        post.reload()
        self.assertEqual(post.hits, 10)

        BlogPost.objects.update_one(inc__hits=1)
        post.reload()
        self.assertEqual(post.hits, 11)

        BlogPost.objects.update_one(dec__hits=1)
        post.reload()
        self.assertEqual(post.hits, 10)

        BlogPost.objects.update(push__tags='mongo')
        post.reload()
        self.assertTrue('mongo' in post.tags)

        tags = post.tags[:-1]
        BlogPost.objects.update(pop__tags=1)
        post.reload()
        self.assertEqual(post.tags, tags)

        BlogPost.objects.update_one(add_to_set__tags='unique')
        BlogPost.objects.update_one(add_to_set__tags='unique')
        post.reload()
        self.assertEqual(post.tags.count('unique'), 1)

        self.assertNotEqual(post.hits, None)
        BlogPost.objects.update_one(unset__hits=1)
        post.reload()
        self.assertEqual(post.hits, None)

        BlogPost.drop_collection()

    def test_update_push_and_pull_add_to_set(self):
        """Ensure that the 'pull' update operation works correctly.
        """
        class BlogPost(Document):
            slug = StringField()
            tags = ListField(StringField())

        BlogPost.drop_collection()

        post = BlogPost(slug="test")
        post.save()

        BlogPost.objects.filter(id=post.id).update(push__tags="code")
        post.reload()
        self.assertEqual(post.tags, ["code"])

        BlogPost.objects.filter(id=post.id).update(push__tags="mongodb")
        post.reload()
        self.assertEqual(post.tags, ["code", "mongodb"])

        BlogPost.objects(slug="test").update(pull__tags="code")
        post.reload()
        self.assertEqual(post.tags, ["mongodb"])

        BlogPost.objects(slug="test").update(pull_all__tags=["mongodb", "code"])
        post.reload()
        self.assertEqual(post.tags, [])

        BlogPost.objects(slug="test").update(__raw__={"$addToSet": {"tags": {"$each": ["code", "mongodb", "code"]}}})
        post.reload()
        self.assertEqual(post.tags, ["code", "mongodb"])

    def test_add_to_set_each(self):
        class Item(Document):
            name = StringField(required=True)
            description = StringField(max_length=50)
            parents = ListField(ReferenceField('self'))

        Item.drop_collection()

        item = Item(name='test item').save()
        parent_1 = Item(name='parent 1').save()
        parent_2 = Item(name='parent 2').save()

        item.update(add_to_set__parents=[parent_1, parent_2, parent_1])
        item.reload()

        self.assertEqual([parent_1, parent_2], item.parents)

    def test_pull_nested(self):

        class User(Document):
            name = StringField()

        class Collaborator(EmbeddedDocument):
            user = StringField()

            def __unicode__(self):
                return '%s' % self.user

        class Site(Document):
            name = StringField(max_length=75, unique=True, required=True)
            collaborators = ListField(EmbeddedDocumentField(Collaborator))

        Site.drop_collection()

        c = Collaborator(user='Esteban')
        s = Site(name="test", collaborators=[c])
        s.save()

        Site.objects(id=s.id).update_one(pull__collaborators__user='Esteban')
        self.assertEqual(Site.objects.first().collaborators, [])

        def pull_all():
            Site.objects(id=s.id).update_one(pull_all__collaborators__user=['Ross'])

        self.assertRaises(InvalidQueryError, pull_all)

    def test_update_one_pop_generic_reference(self):

        class BlogTag(Document):
            name = StringField(required=True)

        class BlogPost(Document):
            slug = StringField()
            tags = ListField(ReferenceField(BlogTag), required=True)

        BlogPost.drop_collection()
        BlogTag.drop_collection()

        tag_1 = BlogTag(name='code')
        tag_1.save()
        tag_2 = BlogTag(name='mongodb')
        tag_2.save()

        post = BlogPost(slug="test", tags=[tag_1])
        post.save()

        post = BlogPost(slug="test-2", tags=[tag_1, tag_2])
        post.save()
        self.assertEqual(len(post.tags), 2)

        BlogPost.objects(slug="test-2").update_one(pop__tags=-1)

        post.reload()
        self.assertEqual(len(post.tags), 1)

        BlogPost.drop_collection()
        BlogTag.drop_collection()

    def test_editting_embedded_objects(self):

        class BlogTag(EmbeddedDocument):
            name = StringField(required=True)

        class BlogPost(Document):
            slug = StringField()
            tags = ListField(EmbeddedDocumentField(BlogTag), required=True)

        BlogPost.drop_collection()

        tag_1 = BlogTag(name='code')
        tag_2 = BlogTag(name='mongodb')

        post = BlogPost(slug="test", tags=[tag_1])
        post.save()

        post = BlogPost(slug="test-2", tags=[tag_1, tag_2])
        post.save()
        self.assertEqual(len(post.tags), 2)

        BlogPost.objects(slug="test-2").update_one(set__tags__0__name="python")
        post.reload()
        self.assertEqual(post.tags[0].name, 'python')

        BlogPost.objects(slug="test-2").update_one(pop__tags=-1)
        post.reload()
        self.assertEqual(len(post.tags), 1)

        BlogPost.drop_collection()

    def test_set_list_embedded_documents(self):

        class Author(EmbeddedDocument):
            name = StringField()

        class Message(Document):
            title = StringField()
            authors = ListField(EmbeddedDocumentField('Author'))

        Message.drop_collection()

        message = Message(title="hello", authors=[Author(name="Harry")])
        message.save()

        Message.objects(authors__name="Harry").update_one(
            set__authors__S=Author(name="Ross"))

        message = message.reload()
        self.assertEqual(message.authors[0].name, "Ross")

        Message.objects(authors__name="Ross").update_one(
            set__authors=[Author(name="Harry"),
                          Author(name="Ross"),
                          Author(name="Adam")])

        message = message.reload()
        self.assertEqual(message.authors[0].name, "Harry")
        self.assertEqual(message.authors[1].name, "Ross")
        self.assertEqual(message.authors[2].name, "Adam")

    def test_order_by(self):
        """Ensure that QuerySets may be ordered.
        """
        self.Person(name="User B", age=40).save()
        self.Person(name="User A", age=20).save()
        self.Person(name="User C", age=30).save()

        names = [p.name for p in self.Person.objects.order_by('-age')]
        self.assertEqual(names, ['User B', 'User C', 'User A'])

        names = [p.name for p in self.Person.objects.order_by('+age')]
        self.assertEqual(names, ['User A', 'User C', 'User B'])

        names = [p.name for p in self.Person.objects.order_by('age')]
        self.assertEqual(names, ['User A', 'User C', 'User B'])

        ages = [p.age for p in self.Person.objects.order_by('-name')]
        self.assertEqual(ages, [30, 40, 20])

    def test_order_by_optional(self):
        class BlogPost(Document):
            title = StringField()
            published_date = DateTimeField(required=False)

        BlogPost.drop_collection()

        blog_post_3 = BlogPost(title="Blog Post #3",
                               published_date=datetime(2010, 1, 6, 0, 0, 0))
        blog_post_2 = BlogPost(title="Blog Post #2",
                               published_date=datetime(2010, 1, 5, 0, 0, 0))
        blog_post_4 = BlogPost(title="Blog Post #4",
                               published_date=datetime(2010, 1, 7, 0, 0, 0))
        blog_post_1 = BlogPost(title="Blog Post #1", published_date=None)

        blog_post_3.save()
        blog_post_1.save()
        blog_post_4.save()
        blog_post_2.save()

        expected = [blog_post_1, blog_post_2, blog_post_3, blog_post_4]
        self.assertSequence(BlogPost.objects.order_by('published_date'),
                            expected)
        self.assertSequence(BlogPost.objects.order_by('+published_date'),
                            expected)

        expected.reverse()
        self.assertSequence(BlogPost.objects.order_by('-published_date'),
                            expected)

    def test_order_by_list(self):
        class BlogPost(Document):
            title = StringField()
            published_date = DateTimeField(required=False)

        BlogPost.drop_collection()

        blog_post_1 = BlogPost(title="A",
                               published_date=datetime(2010, 1, 6, 0, 0, 0))
        blog_post_2 = BlogPost(title="B",
                               published_date=datetime(2010, 1, 6, 0, 0, 0))
        blog_post_3 = BlogPost(title="C",
                               published_date=datetime(2010, 1, 7, 0, 0, 0))

        blog_post_2.save()
        blog_post_3.save()
        blog_post_1.save()

        qs = BlogPost.objects.order_by('published_date', 'title')
        expected = [blog_post_1, blog_post_2, blog_post_3]
        self.assertSequence(qs, expected)

        qs = BlogPost.objects.order_by('-published_date', '-title')
        expected.reverse()
        self.assertSequence(qs, expected)

    def test_order_by_chaining(self):
        """Ensure that an order_by query chains properly and allows .only()
        """
        self.Person(name="User B", age=40).save()
        self.Person(name="User A", age=20).save()
        self.Person(name="User C", age=30).save()

        only_age = self.Person.objects.order_by('-age').only('age')

        names = [p.name for p in only_age]
        ages = [p.age for p in only_age]

        # The .only('age') clause should mean that all names are None
        self.assertEqual(names, [None, None, None])
        self.assertEqual(ages, [40, 30, 20])

        qs = self.Person.objects.all().order_by('-age')
        qs = qs.limit(10)
        ages = [p.age for p in qs]
        self.assertEqual(ages, [40, 30, 20])

        qs = self.Person.objects.all().limit(10)
        qs = qs.order_by('-age')

        ages = [p.age for p in qs]
        self.assertEqual(ages, [40, 30, 20])

        qs = self.Person.objects.all().skip(0)
        qs = qs.order_by('-age')
        ages = [p.age for p in qs]
        self.assertEqual(ages, [40, 30, 20])

    def test_confirm_order_by_reference_wont_work(self):
        """Ordering by reference is not possible.  Use map / reduce.. or
        denormalise"""

        class Author(Document):
            author = ReferenceField(self.Person)

        Author.drop_collection()

        person_a = self.Person(name="User A", age=20)
        person_a.save()
        person_b = self.Person(name="User B", age=40)
        person_b.save()
        person_c = self.Person(name="User C", age=30)
        person_c.save()

        Author(author=person_a).save()
        Author(author=person_b).save()
        Author(author=person_c).save()

        names = [a.author.name for a in Author.objects.order_by('-author__age')]
        self.assertEqual(names, ['User A', 'User B', 'User C'])

    def test_average(self):
        """Ensure that field can be averaged correctly."""
        ages = [0, 23, 54, 12, 94, 27]
        for i, age in enumerate(ages):
            self.Person(name='test%s' % i, age=age).save()
        self.Person(name='ageless person').save()

        avg = float(sum(ages)) / (len(ages))
        self.assertAlmostEqual(int(self.Person.objects.average('age')), avg)

    def test_average_over_zero(self):
        self.Person(name='person', age=0).save()
        self.assertEqual(int(self.Person.objects.average('age')), 0)

    def test_sum(self):
        """Ensure that field can be summed over correctly."""
        ages = [0, 23, 54, 12, 94, 27]
        for i, age in enumerate(ages):
            self.Person(name='test%s' % i, age=age).save()
        self.Person(name='ageless person').save()

        self.assertEqual(int(self.Person.objects.sum('age')), sum(ages))

    def test_average_over_db_field(self):
        class UserVisit(Document):
            num_visits = IntField(db_field='visits')

        UserVisit.drop_collection()

        UserVisit.objects.create(num_visits=20)
        UserVisit.objects.create(num_visits=10)

        self.assertEqual(UserVisit.objects.average('num_visits'), 15)

    def test_sum_over_db_field(self):
        class UserVisit(Document):
            num_visits = IntField(db_field='visits')

        UserVisit.drop_collection()

        UserVisit.objects.create(num_visits=10)
        UserVisit.objects.create(num_visits=5)

        self.assertEqual(UserVisit.objects.sum('num_visits'), 15)

    def test_distinct(self):
        """Ensure that the QuerySet.distinct method works.
        """
        self.Person(name='Mr Orange', age=20).save()
        self.Person(name='Mr White', age=20).save()
        self.Person(name='Mr Orange', age=30).save()
        self.Person(name='Mr Pink', age=30).save()
        self.assertEqual(set(self.Person.objects.distinct('name')),
                         set(['Mr Orange', 'Mr White', 'Mr Pink']))
        self.assertEqual(set(self.Person.objects.distinct('age')),
                         set([20, 30]))
        self.assertEqual(set(self.Person.objects(age=30).distinct('name')),
                         set(['Mr Orange', 'Mr Pink']))

    def test_distinct_handles_references(self):
        class Foo(Document):
            bar = ReferenceField("Bar")

        class Bar(Document):
            text = StringField()

        Bar.drop_collection()
        Foo.drop_collection()

        bar = Bar(text="hi")
        bar.save()

        foo = Foo(bar=bar)
        foo.save()

        self.assertEqual(Foo.objects.distinct("bar"), [bar])

    def test_distinct_handles_references_to_alias(self):
        register_connection('testdb', 'mongoenginetest2')

        class Foo(Document):
            bar = ReferenceField("Bar")
            meta = {'db_alias': 'testdb'}

        class Bar(Document):
            text = StringField()
            meta = {'db_alias': 'testdb'}

        Bar.drop_collection()
        Foo.drop_collection()

        bar = Bar(text="hi")
        bar.save()

        foo = Foo(bar=bar)
        foo.save()

        self.assertEqual(Foo.objects.distinct("bar"), [bar])

    def test_distinct_handles_db_field(self):
        """Ensure that distinct resolves field name to db_field as expected.
        """
        class Product(Document):
            product_id = IntField(db_field='pid')

        Product.drop_collection()

        Product(product_id=1).save()
        Product(product_id=2).save()
        Product(product_id=1).save()

        self.assertEqual(set(Product.objects.distinct('product_id')),
                         set([1, 2]))
        self.assertEqual(set(Product.objects.distinct('pid')),
                         set([1, 2]))

        Product.drop_collection()

    def test_custom_manager(self):
        """Ensure that custom QuerySetManager instances work as expected.
        """
        class BlogPost(Document):
            tags = ListField(StringField())
            deleted = BooleanField(default=False)
            date = DateTimeField(default=datetime.now)

            @queryset_manager
            def objects(cls, qryset):
                opts = {"deleted": False}
                return qryset(**opts)

            @queryset_manager
            def music_posts(doc_cls, queryset, deleted=False):
                return queryset(tags='music',
                                deleted=deleted).order_by('date')

        BlogPost.drop_collection()

        post1 = BlogPost(tags=['music', 'film']).save()
        post2 = BlogPost(tags=['music']).save()
        post3 = BlogPost(tags=['film', 'actors']).save()
        post4 = BlogPost(tags=['film', 'actors', 'music'], deleted=True).save()

        self.assertEqual([p.id for p in BlogPost.objects()],
                         [post1.id, post2.id, post3.id])
        self.assertEqual([p.id for p in BlogPost.music_posts()],
                         [post1.id, post2.id])

        self.assertEqual([p.id for p in BlogPost.music_posts(True)],
                         [post4.id])

        BlogPost.drop_collection()

    def test_custom_manager_overriding_objects_works(self):

        class Foo(Document):
            bar = StringField(default='bar')
            active = BooleanField(default=False)

            @queryset_manager
            def objects(doc_cls, queryset):
                return queryset(active=True)

            @queryset_manager
            def with_inactive(doc_cls, queryset):
                return queryset(active=False)

        Foo.drop_collection()

        Foo(active=True).save()
        Foo(active=False).save()

        self.assertEqual(1, Foo.objects.count())
        self.assertEqual(1, Foo.with_inactive.count())

        Foo.with_inactive.first().delete()
        self.assertEqual(0, Foo.with_inactive.count())
        self.assertEqual(1, Foo.objects.count())

    def test_inherit_objects(self):

        class Foo(Document):
            meta = {'allow_inheritance': True}
            active = BooleanField(default=True)

            @queryset_manager
            def objects(klass, queryset):
                return queryset(active=True)

        class Bar(Foo):
            pass

        Bar.drop_collection()
        Bar.objects.create(active=False)
        self.assertEqual(0, Bar.objects.count())

    def test_inherit_objects_override(self):

        class Foo(Document):
            meta = {'allow_inheritance': True}
            active = BooleanField(default=True)

            @queryset_manager
            def objects(klass, queryset):
                return queryset(active=True)

        class Bar(Foo):
            @queryset_manager
            def objects(klass, queryset):
                return queryset(active=False)

        Bar.drop_collection()
        Bar.objects.create(active=False)
        self.assertEqual(0, Foo.objects.count())
        self.assertEqual(1, Bar.objects.count())

    def test_query_value_conversion(self):
        """Ensure that query values are properly converted when necessary.
        """
        class BlogPost(Document):
            author = ReferenceField(self.Person)

        BlogPost.drop_collection()

        person = self.Person(name='test', age=30)
        person.save()

        post = BlogPost(author=person)
        post.save()

        # Test that query may be performed by providing a document as a value
        # while using a ReferenceField's name - the document should be
        # converted to an DBRef, which is legal, unlike a Document object
        post_obj = BlogPost.objects(author=person).first()
        self.assertEqual(post.id, post_obj.id)

        # Test that lists of values work when using the 'in', 'nin' and 'all'
        post_obj = BlogPost.objects(author__in=[person]).first()
        self.assertEqual(post.id, post_obj.id)

        BlogPost.drop_collection()

    def test_update_value_conversion(self):
        """Ensure that values used in updates are converted before use.
        """
        class Group(Document):
            members = ListField(ReferenceField(self.Person))

        Group.drop_collection()

        user1 = self.Person(name='user1')
        user1.save()
        user2 = self.Person(name='user2')
        user2.save()

        group = Group()
        group.save()

        Group.objects(id=group.id).update(set__members=[user1, user2])
        group.reload()

        self.assertTrue(len(group.members) == 2)
        self.assertEqual(group.members[0].name, user1.name)
        self.assertEqual(group.members[1].name, user2.name)

        Group.drop_collection()

    def test_dict_with_custom_baseclass(self):
        """Ensure DictField working with custom base clases.
        """
        class Test(Document):
            testdict = DictField()

        Test.drop_collection()

        t = Test(testdict={'f': 'Value'})
        t.save()

        self.assertEqual(Test.objects(testdict__f__startswith='Val').count(), 1)
        self.assertEqual(Test.objects(testdict__f='Value').count(), 1)
        Test.drop_collection()

        class Test(Document):
            testdict = DictField(basecls=StringField)

        t = Test(testdict={'f': 'Value'})
        t.save()

        self.assertEqual(Test.objects(testdict__f='Value').count(), 1)
        self.assertEqual(Test.objects(testdict__f__startswith='Val').count(), 1)
        Test.drop_collection()

    def test_bulk(self):
        """Ensure bulk querying by object id returns a proper dict.
        """
        class BlogPost(Document):
            title = StringField()

        BlogPost.drop_collection()

        post_1 = BlogPost(title="Post #1")
        post_2 = BlogPost(title="Post #2")
        post_3 = BlogPost(title="Post #3")
        post_4 = BlogPost(title="Post #4")
        post_5 = BlogPost(title="Post #5")

        post_1.save()
        post_2.save()
        post_3.save()
        post_4.save()
        post_5.save()

        ids = [post_1.id, post_2.id, post_5.id]
        objects = BlogPost.objects.in_bulk(ids)

        self.assertEqual(len(objects), 3)

        self.assertTrue(post_1.id in objects)
        self.assertTrue(post_2.id in objects)
        self.assertTrue(post_5.id in objects)

        self.assertTrue(objects[post_1.id].title == post_1.title)
        self.assertTrue(objects[post_2.id].title == post_2.title)
        self.assertTrue(objects[post_5.id].title == post_5.title)

        BlogPost.drop_collection()

    def tearDown(self):
        self.Person.drop_collection()

    def test_custom_querysets(self):
        """Ensure that custom QuerySet classes may be used.
        """
        class CustomQuerySet(QuerySet):
            def not_empty(self):
                return self.count() > 0

        class Post(Document):
            meta = {'queryset_class': CustomQuerySet}

        Post.drop_collection()

        self.assertTrue(isinstance(Post.objects, CustomQuerySet))
        self.assertFalse(Post.objects.not_empty())

        Post().save()
        self.assertTrue(Post.objects.not_empty())

        Post.drop_collection()

    def test_custom_querysets_set_manager_directly(self):
        """Ensure that custom QuerySet classes may be used.
        """

        class CustomQuerySet(QuerySet):
            def not_empty(self):
                return self.count() > 0

        class CustomQuerySetManager(QuerySetManager):
            queryset_class = CustomQuerySet

        class Post(Document):
            objects = CustomQuerySetManager()

        Post.drop_collection()

        self.assertTrue(isinstance(Post.objects, CustomQuerySet))
        self.assertFalse(Post.objects.not_empty())

        Post().save()
        self.assertTrue(Post.objects.not_empty())

        Post.drop_collection()

    def test_custom_querysets_managers_directly(self):
        """Ensure that custom QuerySet classes may be used.
        """

        class CustomQuerySetManager(QuerySetManager):

            @staticmethod
            def get_queryset(doc_cls, queryset):
                return queryset(is_published=True)

        class Post(Document):
            is_published = BooleanField(default=False)
            published = CustomQuerySetManager()

        Post.drop_collection()

        Post().save()
        Post(is_published=True).save()
        self.assertEqual(Post.objects.count(), 2)
        self.assertEqual(Post.published.count(), 1)

        Post.drop_collection()

    def test_custom_querysets_inherited(self):
        """Ensure that custom QuerySet classes may be used.
        """

        class CustomQuerySet(QuerySet):
            def not_empty(self):
                return self.count() > 0

        class Base(Document):
            meta = {'abstract': True, 'queryset_class': CustomQuerySet}

        class Post(Base):
            pass

        Post.drop_collection()
        self.assertTrue(isinstance(Post.objects, CustomQuerySet))
        self.assertFalse(Post.objects.not_empty())

        Post().save()
        self.assertTrue(Post.objects.not_empty())

        Post.drop_collection()

    def test_custom_querysets_inherited_direct(self):
        """Ensure that custom QuerySet classes may be used.
        """

        class CustomQuerySet(QuerySet):
            def not_empty(self):
                return self.count() > 0

        class CustomQuerySetManager(QuerySetManager):
            queryset_class = CustomQuerySet

        class Base(Document):
            meta = {'abstract': True}
            objects = CustomQuerySetManager()

        class Post(Base):
            pass

        Post.drop_collection()
        self.assertTrue(isinstance(Post.objects, CustomQuerySet))
        self.assertFalse(Post.objects.not_empty())

        Post().save()
        self.assertTrue(Post.objects.not_empty())

        Post.drop_collection()

    def test_count_limit_and_skip(self):
        class Post(Document):
            title = StringField()

        Post.drop_collection()

        for i in range(10):
            Post(title="Post %s" % i).save()

        self.assertEqual(5, Post.objects.limit(5).skip(5).count())

        self.assertEqual(10, Post.objects.limit(5).skip(5).count(with_limit_and_skip=False))

    def test_call_after_limits_set(self):
        """Ensure that re-filtering after slicing works
        """
        class Post(Document):
            title = StringField()

        Post.drop_collection()

        Post(title="Post 1").save()
        Post(title="Post 2").save()

        posts = Post.objects.all()[0:1]
        self.assertEqual(len(list(posts())), 1)

        Post.drop_collection()

    def test_order_then_filter(self):
        """Ensure that ordering still works after filtering.
        """
        class Number(Document):
            n = IntField()

        Number.drop_collection()

        n2 = Number.objects.create(n=2)
        n1 = Number.objects.create(n=1)

        self.assertEqual(list(Number.objects), [n2, n1])
        self.assertEqual(list(Number.objects.order_by('n')), [n1, n2])
        self.assertEqual(list(Number.objects.order_by('n').filter()), [n1, n2])

        Number.drop_collection()

    def test_clone(self):
        """Ensure that cloning clones complex querysets
        """
        class Number(Document):
            n = IntField()

        Number.drop_collection()

        for i in range(1, 101):
            t = Number(n=i)
            t.save()

        test = Number.objects
        test2 = test.clone()
        self.assertFalse(test == test2)
        self.assertEqual(test.count(), test2.count())

        test = test.filter(n__gt=11)
        test2 = test.clone()
        self.assertFalse(test == test2)
        self.assertEqual(test.count(), test2.count())

        test = test.limit(10)
        test2 = test.clone()
        self.assertFalse(test == test2)
        self.assertEqual(test.count(), test2.count())

        Number.drop_collection()

    def test_unset_reference(self):
        class Comment(Document):
            text = StringField()

        class Post(Document):
            comment = ReferenceField(Comment)

        Comment.drop_collection()
        Post.drop_collection()

        comment = Comment.objects.create(text='test')
        post = Post.objects.create(comment=comment)

        self.assertEqual(post.comment, comment)
        Post.objects.update(unset__comment=1)
        post.reload()
        self.assertEqual(post.comment, None)

        Comment.drop_collection()
        Post.drop_collection()

    def test_order_works_with_custom_db_field_names(self):
        class Number(Document):
            n = IntField(db_field='number')

        Number.drop_collection()

        n2 = Number.objects.create(n=2)
        n1 = Number.objects.create(n=1)

        self.assertEqual(list(Number.objects), [n2,n1])
        self.assertEqual(list(Number.objects.order_by('n')), [n1,n2])

        Number.drop_collection()

    def test_order_works_with_primary(self):
        """Ensure that order_by and primary work.
        """
        class Number(Document):
            n = IntField(primary_key=True)

        Number.drop_collection()

        Number(n=1).save()
        Number(n=2).save()
        Number(n=3).save()

        numbers = [n.n for n in Number.objects.order_by('-n')]
        self.assertEqual([3, 2, 1], numbers)

        numbers = [n.n for n in Number.objects.order_by('+n')]
        self.assertEqual([1, 2, 3], numbers)
        Number.drop_collection()

    def test_ensure_index(self):
        """Ensure that manual creation of indexes works.
        """
        class Comment(Document):
            message = StringField()
            meta = {'allow_inheritance': True}

        Comment.ensure_index('message')

        info = Comment.objects._collection.index_information()
        info = [(value['key'],
                 value.get('unique', False),
                 value.get('sparse', False))
                for key, value in info.items()]
        self.assertTrue(([('_cls', 1), ('message', 1)], False, False) in info)

    def test_scalar(self):

        class Organization(Document):
            id = ObjectIdField('_id')
            name = StringField()

        class User(Document):
            id = ObjectIdField('_id')
            name = StringField()
            organization = ObjectIdField()

        User.drop_collection()
        Organization.drop_collection()

        whitehouse = Organization(name="White House")
        whitehouse.save()
        User(name="Bob Dole", organization=whitehouse.id).save()

        # Efficient way to get all unique organization names for a given
        # set of users (Pretend this has additional filtering.)
        user_orgs = set(User.objects.scalar('organization'))
        orgs = Organization.objects(id__in=user_orgs).scalar('name')
        self.assertEqual(list(orgs), ['White House'])

        # Efficient for generating listings, too.
        orgs = Organization.objects.scalar('name').in_bulk(list(user_orgs))
        user_map = User.objects.scalar('name', 'organization')
        user_listing = [(user, orgs[org]) for user, org in user_map]
        self.assertEqual([("Bob Dole", "White House")], user_listing)

    def test_scalar_simple(self):
        class TestDoc(Document):
            x = IntField()
            y = BooleanField()

        TestDoc.drop_collection()

        TestDoc(x=10, y=True).save()
        TestDoc(x=20, y=False).save()
        TestDoc(x=30, y=True).save()

        plist = list(TestDoc.objects.scalar('x', 'y'))

        self.assertEqual(len(plist), 3)
        self.assertEqual(plist[0], (10, True))
        self.assertEqual(plist[1], (20, False))
        self.assertEqual(plist[2], (30, True))

        class UserDoc(Document):
            name = StringField()
            age = IntField()

        UserDoc.drop_collection()

        UserDoc(name="Wilson Jr", age=19).save()
        UserDoc(name="Wilson", age=43).save()
        UserDoc(name="Eliana", age=37).save()
        UserDoc(name="Tayza", age=15).save()

        ulist = list(UserDoc.objects.scalar('name', 'age'))

        self.assertEqual(ulist, [
                ('Wilson Jr', 19),
                ('Wilson', 43),
                ('Eliana', 37),
                ('Tayza', 15)])

        ulist = list(UserDoc.objects.scalar('name').order_by('age'))

        self.assertEqual(ulist, [
                ('Tayza'),
                ('Wilson Jr'),
                ('Eliana'),
                ('Wilson')])

    def test_scalar_embedded(self):
        class Profile(EmbeddedDocument):
            name = StringField()
            age = IntField()

        class Locale(EmbeddedDocument):
            city = StringField()
            country = StringField()

        class Person(Document):
            profile = EmbeddedDocumentField(Profile)
            locale = EmbeddedDocumentField(Locale)

        Person.drop_collection()

        Person(profile=Profile(name="Wilson Jr", age=19),
               locale=Locale(city="Corumba-GO", country="Brazil")).save()

        Person(profile=Profile(name="Gabriel Falcao", age=23),
               locale=Locale(city="New York", country="USA")).save()

        Person(profile=Profile(name="Lincoln de souza", age=28),
               locale=Locale(city="Belo Horizonte", country="Brazil")).save()

        Person(profile=Profile(name="Walter cruz", age=30),
               locale=Locale(city="Brasilia", country="Brazil")).save()

        self.assertEqual(
            list(Person.objects.order_by('profile__age').scalar('profile__name')),
            ['Wilson Jr', 'Gabriel Falcao', 'Lincoln de souza', 'Walter cruz'])

        ulist = list(Person.objects.order_by('locale.city')
                     .scalar('profile__name', 'profile__age', 'locale__city'))
        self.assertEqual(ulist,
                         [('Lincoln de souza', 28, 'Belo Horizonte'),
                          ('Walter cruz', 30, 'Brasilia'),
                          ('Wilson Jr', 19, 'Corumba-GO'),
                          ('Gabriel Falcao', 23, 'New York')])

    def test_scalar_reference_field(self):
        class State(Document):
            name = StringField()

        class Person(Document):
            name = StringField()
            state = ReferenceField(State)

        State.drop_collection()
        Person.drop_collection()

        s1 = State(name="Goias")
        s1.save()

        Person(name="Wilson JR", state=s1).save()

        plist = list(Person.objects.scalar('name', 'state'))
        self.assertEqual(plist, [('Wilson JR', s1)])

    def test_scalar_generic_reference_field(self):
        class State(Document):
            name = StringField()

        class Person(Document):
            name = StringField()
            state = GenericReferenceField()

        State.drop_collection()
        Person.drop_collection()

        s1 = State(name="Goias")
        s1.save()

        Person(name="Wilson JR", state=s1).save()

        plist = list(Person.objects.scalar('name', 'state'))
        self.assertEqual(plist, [('Wilson JR', s1)])

    def test_scalar_db_field(self):

        class TestDoc(Document):
            x = IntField()
            y = BooleanField()

        TestDoc.drop_collection()

        TestDoc(x=10, y=True).save()
        TestDoc(x=20, y=False).save()
        TestDoc(x=30, y=True).save()

        plist = list(TestDoc.objects.scalar('x', 'y'))
        self.assertEqual(len(plist), 3)
        self.assertEqual(plist[0], (10, True))
        self.assertEqual(plist[1], (20, False))
        self.assertEqual(plist[2], (30, True))

    def test_scalar_primary_key(self):

        class SettingValue(Document):
            key = StringField(primary_key=True)
            value = StringField()

        SettingValue.drop_collection()
        s = SettingValue(key="test", value="test value")
        s.save()

        val = SettingValue.objects.scalar('key', 'value')
        self.assertEqual(list(val), [('test', 'test value')])

    def test_scalar_cursor_behaviour(self):
        """Ensure that a query returns a valid set of results.
        """
        person1 = self.Person(name="User A", age=20)
        person1.save()
        person2 = self.Person(name="User B", age=30)
        person2.save()

        # Find all people in the collection
        people = self.Person.objects.scalar('name')
        self.assertEqual(people.count(), 2)
        results = list(people)
        self.assertEqual(results[0], "User A")
        self.assertEqual(results[1], "User B")

        # Use a query to filter the people found to just person1
        people = self.Person.objects(age=20).scalar('name')
        self.assertEqual(people.count(), 1)
        person = next(people)
        self.assertEqual(person, "User A")

        # Test limit
        people = list(self.Person.objects.limit(1).scalar('name'))
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0], 'User A')

        # Test skip
        people = list(self.Person.objects.skip(1).scalar('name'))
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0], 'User B')

        person3 = self.Person(name="User C", age=40)
        person3.save()

        # Test slice limit
        people = list(self.Person.objects[:2].scalar('name'))
        self.assertEqual(len(people), 2)
        self.assertEqual(people[0], 'User A')
        self.assertEqual(people[1], 'User B')

        # Test slice skip
        people = list(self.Person.objects[1:].scalar('name'))
        self.assertEqual(len(people), 2)
        self.assertEqual(people[0], 'User B')
        self.assertEqual(people[1], 'User C')

        # Test slice limit and skip
        people = list(self.Person.objects[1:2].scalar('name'))
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0], 'User B')

        people = list(self.Person.objects[1:1].scalar('name'))
        self.assertEqual(len(people), 0)

        # Test slice out of range
        people = list(self.Person.objects.scalar('name')[80000:80001])
        self.assertEqual(len(people), 0)

        # Test larger slice __repr__
        self.Person.objects.delete()
        for i in range(55):
            self.Person(name='A%s' % i, age=i).save()

        self.assertEqual(self.Person.objects.scalar('name').count(), 55)
        self.assertEqual("A0", "%s" % self.Person.objects.order_by('name').scalar('name').first())
        self.assertEqual("A0", "%s" % self.Person.objects.scalar('name').order_by('name')[0])
        if PY3:
            self.assertEqual("['A1', 'A2']",  "%s" % self.Person.objects.order_by('age').scalar('name')[1:3])
            self.assertEqual("['A51', 'A52']",  "%s" % self.Person.objects.order_by('age').scalar('name')[51:53])
        else:
            self.assertEqual("[u'A1', u'A2']",  "%s" % self.Person.objects.order_by('age').scalar('name')[1:3])
            self.assertEqual("[u'A51', u'A52']",  "%s" % self.Person.objects.order_by('age').scalar('name')[51:53])

        # with_id and in_bulk
        person = self.Person.objects.order_by('name').first()
        self.assertEqual("A0", "%s" % self.Person.objects.scalar('name').with_id(person.id))

        pks = self.Person.objects.order_by('age').scalar('pk')[1:3]
        if PY3:
            self.assertEqual("['A1', 'A2']",  "%s" % sorted(self.Person.objects.scalar('name').in_bulk(list(pks)).values()))
        else:
            self.assertEqual("[u'A1', u'A2']",  "%s" % sorted(self.Person.objects.scalar('name').in_bulk(list(pks)).values()))

    def test_elem_match(self):
        class Foo(EmbeddedDocument):
            shape = StringField()
            color = StringField()
            thick = BooleanField()
            meta = {'allow_inheritance': False}

        class Bar(Document):
            foo = ListField(EmbeddedDocumentField(Foo))
            meta = {'allow_inheritance': False}

        Bar.drop_collection()

        b1 = Bar(foo=[Foo(shape= "square", color ="purple", thick = False),
                      Foo(shape= "circle", color ="red", thick = True)])
        b1.save()

        b2 = Bar(foo=[Foo(shape= "square", color ="red", thick = True),
                      Foo(shape= "circle", color ="purple", thick = False)])
        b2.save()

        ak = list(Bar.objects(foo__match={'shape': "square", "color": "purple"}))
        self.assertEqual([b1], ak)

    def test_upsert_includes_cls(self):
        """Upserts should include _cls information for inheritable classes
        """

        class Test(Document):
            test = StringField()

        Test.drop_collection()
        Test.objects(test='foo').update_one(upsert=True, set__test='foo')
        self.assertFalse('_cls' in Test._collection.find_one())

        class Test(Document):
            meta = {'allow_inheritance': True}
            test = StringField()

        Test.drop_collection()

        Test.objects(test='foo').update_one(upsert=True, set__test='foo')
        self.assertTrue('_cls' in Test._collection.find_one())

    def test_clear_cls_query(self):
        class Test(Document):
            meta = {'allow_inheritance': True}
            test = StringField()

        Test.drop_collection()
        Test.objects.create(test='foo')
        tests = Test.objects.clear_cls_query().all()
        self.assertEqual(tests.count(), 1)
        self.assertEqual(tests._initial_query, {})

    def test_read_preference(self):
        class Bar(Document):
            txt = StringField()

            meta = {
                'indexes': [ 'txt' ]
            }

        Bar.drop_collection()
        bars = list(Bar.objects(read_preference=ReadPreference.PRIMARY))
        self.assertEqual([], bars)

        with self.assertRaises(TypeError) as cm:
            Bar.objects(read_preference='Primary')
        self.assertEqual(
            str(cm.exception), "'Primary' is not a read preference."
        )

        # read_preference as a kwarg
        bars = Bar.objects(read_preference=ReadPreference.SECONDARY_PREFERRED)
        self.assertEqual(
            bars._read_preference, ReadPreference.SECONDARY_PREFERRED
        )
        self.assertEqual(
            bars._cursor.collection.read_preference,
            ReadPreference.SECONDARY_PREFERRED
        )

        # read_preference as a query set method
        bars = Bar.objects.read_preference(ReadPreference.SECONDARY)
        self.assertEqual(
            bars._read_preference,
            ReadPreference.SECONDARY
        )
        self.assertEqual(
            bars._cursor.collection.read_preference,
            ReadPreference.SECONDARY
        )

        # read_preference after skip
        bars = Bar.objects.skip(1) \
            .read_preference(ReadPreference.SECONDARY_PREFERRED)
        self.assertEqual(
            bars._read_preference, ReadPreference.SECONDARY_PREFERRED
        )
        self.assertEqual(
            bars._cursor.collection.read_preference,
            ReadPreference.SECONDARY_PREFERRED
        )

        # read_preference after limit
        bars = Bar.objects.limit(1) \
            .read_preference(ReadPreference.SECONDARY)
        self.assertEqual(
            bars._read_preference, ReadPreference.SECONDARY
        )
        self.assertEqual(
            bars._cursor.collection.read_preference,
            ReadPreference.SECONDARY
        )

        # read_preference after order_by
        bars = Bar.objects.order_by('txt') \
            .read_preference(ReadPreference.SECONDARY_PREFERRED)
        self.assertEqual(
            bars._read_preference, ReadPreference.SECONDARY_PREFERRED
        )
        self.assertEqual(
            bars._cursor.collection.read_preference,
            ReadPreference.SECONDARY_PREFERRED
        )

        # read_preference after hint
        bars = Bar.objects.hint([('txt', 1)]) \
            .read_preference(ReadPreference.SECONDARY_PREFERRED)
        self.assertEqual(
            bars._read_preference, ReadPreference.SECONDARY_PREFERRED
        )
        self.assertEqual(
            bars._cursor.collection.read_preference,
            ReadPreference.SECONDARY_PREFERRED
        )

    def test_read_concern(self):
        class Bar(Document):
            txt = StringField()

            meta = {"indexes": ["txt"]}

        Bar.drop_collection()
        bar = Bar.objects.create(txt="xyz")

        bars = list(Bar.objects.read_concern(None))
        assert bars == [bar]

        bars = Bar.objects.read_concern(ReadConcern(level='local'))
        assert bars._read_concern == ReadConcern(level='local')
        assert (
            bars._cursor.collection.read_concern
            == ReadConcern(level='local')
        )

        # Make sure that `.read_concern(...)` does accept string values.
        with self.assertRaises(TypeError):
            Bar.objects.read_concern('local')

        def assert_read_concern(qs, expected_read_concern):
            assert qs._read_concern == expected_read_concern
            assert qs._cursor.collection.read_concern == expected_read_concern

        # Make sure read concern is respected after a `.skip(...)`.
        bars = Bar.objects.skip(1).read_concern(ReadConcern('majority'))
        assert_read_concern(bars, ReadConcern('majority'))

        # Make sure read concern is respected after a `.limit(...)`.
        bars = Bar.objects.limit(1).read_concern(ReadConcern('majority'))
        assert_read_concern(bars, ReadConcern('majority'))

        # Make sure read concern is respected after an `.order_by(...)`.
        bars = Bar.objects.order_by("txt").read_concern(
            ReadConcern('majority')
        )
        assert_read_concern(bars, ReadConcern('majority'))

        # Make sure read concern is respected after a `.hint(...)`.
        bars = Bar.objects.hint([("txt", 1)]).read_concern(
            ReadConcern('majority')
        )
        assert_read_concern(bars, ReadConcern('majority'))

    def test_json_simple(self):

        class Embedded(EmbeddedDocument):
            string = StringField()

        class Doc(Document):
            string = StringField()
            embedded_field = EmbeddedDocumentField(Embedded)

        Doc.drop_collection()
        Doc(string="Hi", embedded_field=Embedded(string="Hi")).save()
        Doc(string="Bye", embedded_field=Embedded(string="Bye")).save()

        Doc().save()
        json_data = Doc.objects.to_json()
        doc_objects = list(Doc.objects)

        self.assertEqual(doc_objects, Doc.objects.from_json(json_data))

    def test_json_complex(self):
        if pymongo.version_tuple[0] <= 2 and pymongo.version_tuple[1] <= 3:
            raise SkipTest("Need pymongo 2.4 as has a fix for DBRefs")

        class EmbeddedDoc(EmbeddedDocument):
            pass

        class Simple(Document):
            pass

        class Doc(Document):
            string_field = StringField(default='1')
            int_field = IntField(default=1)
            float_field = FloatField(default=1.1)
            boolean_field = BooleanField(default=True)
            datetime_field = DateTimeField(default=datetime.now)
            embedded_document_field = EmbeddedDocumentField(
                EmbeddedDoc, default=lambda: EmbeddedDoc())
            list_field = ListField(default=lambda: [1, 2, 3])
            dict_field = DictField(default=lambda: {"hello": "world"})
            objectid_field = ObjectIdField(default=ObjectId)
            reference_field = ReferenceField(Simple, default=lambda: Simple().save())
            map_field = MapField(IntField(), default=lambda: {"simple": 1})
            complex_datetime_field = ComplexDateTimeField(default=datetime.now)
            url_field = URLField(default="http://mongoengine.org")
            dynamic_field = DynamicField(default=1)
            generic_reference_field = GenericReferenceField(default=lambda: Simple().save())
            sorted_list_field = SortedListField(IntField(),
                                                default=lambda: [1, 2, 3])
            email_field = EmailField(default="ross@example.com")
            geo_point_field = GeoPointField(default=lambda: [1, 2])
            sequence_field = SequenceField()
            uuid_field = UUIDField(default=uuid.uuid4)
            generic_embedded_document_field = GenericEmbeddedDocumentField(
                default=lambda: EmbeddedDoc())

        Simple.drop_collection()
        Doc.drop_collection()

        Doc().save()
        json_data = Doc.objects.to_json()
        doc_objects = list(Doc.objects)

        self.assertEqual(doc_objects, Doc.objects.from_json(json_data))

    def test_as_pymongo(self):

        class User(Document):
            id = ObjectIdField('_id')
            name = StringField()
            age = IntField()

        User.drop_collection()
        User(name="Bob Dole", age=89).save()
        User(name="Barack Obama", age=51).save()

        users = User.objects.only('name').as_pymongo()
        results = list(users)
        self.assertTrue(isinstance(results[0], dict))
        self.assertTrue(isinstance(results[1], dict))
        self.assertEqual(results[0]['name'], 'Bob Dole')
        self.assertEqual(results[1]['name'], 'Barack Obama')

        # Make sure _id is included in the results
        users = User.objects.only('id', 'name').as_pymongo()
        results = list(users)
        self.assertTrue('_id' in results[0])
        self.assertTrue('_id' in results[1])

        # Test coerce_types
        users = User.objects.only('name').as_pymongo(coerce_types=True)
        results = list(users)
        self.assertTrue(isinstance(results[0], dict))
        self.assertTrue(isinstance(results[1], dict))
        self.assertEqual(results[0]['name'], 'Bob Dole')
        self.assertEqual(results[1]['name'], 'Barack Obama')

    def test_as_pymongo_json_limit_fields(self):

        class User(Document):
            email = EmailField(unique=True, required=True)
            password_hash = StringField(db_field='password_hash', required=True)
            password_salt = StringField(db_field='password_salt', required=True)

        User.drop_collection()
        User(email="ross@example.com", password_salt="SomeSalt", password_hash="SomeHash").save()

        serialized_user = User.objects.exclude('password_salt', 'password_hash').as_pymongo()[0]
        self.assertEqual(set(['_id', 'email']), set(serialized_user.keys()))

        serialized_user = User.objects.exclude('id', 'password_salt', 'password_hash').to_json()
        self.assertEqual('[{"email": "ross@example.com"}]', serialized_user)

        serialized_user = User.objects.exclude('password_salt').only('email').as_pymongo()[0]
        self.assertEqual(set(['email']), set(serialized_user.keys()))

        serialized_user = User.objects.exclude('password_salt').only('email').to_json()
        self.assertEqual('[{"email": "ross@example.com"}]', serialized_user)

    @unittest.skip("not implemented")
    def test_no_dereference(self):

        class Organization(Document):
            name = StringField()

        class User(Document):
            name = StringField()
            organization = ReferenceField(Organization)

        User.drop_collection()
        Organization.drop_collection()

        whitehouse = Organization(name="White House").save()
        User(name="Bob Dole", organization=whitehouse).save()

        qs = User.objects()
        self.assertTrue(isinstance(qs.first().organization, Organization))
        self.assertFalse(isinstance(qs.no_dereference().first().organization,
                                    Organization))
        self.assertTrue(isinstance(qs.first().organization, Organization))

    def test_cached_queryset(self):
        class Person(Document):
            name = StringField()

        Person.drop_collection()
        for i in range(100):
            Person(name="No: %s" % i).save()

        with query_counter() as q:
            self.assertEqual(q, 0)
            people = Person.objects

            [x for x in people]
            self.assertEqual(100, len(people._result_cache))
            self.assertEqual(None, people._len)
            self.assertEqual(q, 1)

            list(people)
            self.assertEqual(100, people._len)  # Caused by list calling len
            self.assertEqual(q, 1)

            people.count()  # count is cached
            self.assertEqual(q, 1)

    def test_cache_not_cloned(self):

        class User(Document):
            name = StringField()

            def __unicode__(self):
                return self.name

        User.drop_collection()

        User(name="Alice").save()
        User(name="Bob").save()

        users = User.objects.all().order_by('name')
        self.assertEqual("%s" % users, "[<User: Alice>, <User: Bob>]")
        self.assertEqual(2, len(users._result_cache))

        users = users.filter(name="Bob")
        self.assertEqual("%s" % users, "[<User: Bob>]")
        self.assertEqual(1, len(users._result_cache))

    def test_nested_queryset_iterator(self):
        # Try iterating the same queryset twice, nested.
        names = ['Alice', 'Bob', 'Chuck', 'David', 'Eric', 'Francis', 'George']

        class User(Document):
            name = StringField()

            def __unicode__(self):
                return self.name

        User.drop_collection()

        for name in names:
            User(name=name).save()

        users = User.objects.all().order_by('name')
        outer_count = 0
        inner_count = 0
        inner_total_count = 0

        with query_counter() as q:
            self.assertEqual(q, 0)

            self.assertEqual(users.count(), 7)

            for i, outer_user in enumerate(users):
                self.assertEqual(outer_user.name, names[i])
                outer_count += 1
                inner_count = 0

                # Calling len might disrupt the inner loop if there are bugs
                self.assertEqual(users.count(), 7)

                for j, inner_user in enumerate(users):
                    self.assertEqual(inner_user.name, names[j])
                    inner_count += 1
                    inner_total_count += 1

                self.assertEqual(inner_count, 7)  # inner loop should always be executed seven times

            self.assertEqual(outer_count, 7)  # outer loop should be executed seven times total
            self.assertEqual(inner_total_count, 7 * 7)  # inner loop should be executed fourtynine times total

            self.assertEqual(q, 2)

    def test_no_sub_classes(self):
        class A(Document):
            x = IntField()
            y = IntField()

            meta = {'allow_inheritance': True}

        class B(A):
            z = IntField()

        class C(B):
            zz = IntField()

        A.drop_collection()

        A(x=10, y=20).save()
        A(x=15, y=30).save()
        B(x=20, y=40).save()
        B(x=30, y=50).save()
        C(x=40, y=60).save()

        self.assertEqual(A.objects.no_sub_classes().count(), 2)
        self.assertEqual(A.objects.count(), 5)

        self.assertEqual(B.objects.no_sub_classes().count(), 2)
        self.assertEqual(B.objects.count(), 3)

        self.assertEqual(C.objects.no_sub_classes().count(), 1)
        self.assertEqual(C.objects.count(), 1)

        for obj in A.objects.no_sub_classes():
            self.assertEqual(obj.__class__, A)

        for obj in B.objects.no_sub_classes():
            self.assertEqual(obj.__class__, B)

        for obj in C.objects.no_sub_classes():
            self.assertEqual(obj.__class__, C)

    def test_query_reference_to_custom_pk_doc(self):

        class A(Document):
            id = StringField(unique=True, primary_key=True)

        class B(Document):
            a = ReferenceField(A)

        A.drop_collection()
        B.drop_collection()

        a = A.objects.create(id='custom_id')

        b = B.objects.create(a=a)

        self.assertEqual(B.objects.count(), 1)
        self.assertEqual(B.objects.get(a=a).a, a)
        self.assertEqual(B.objects.get(a=a.id).a, a)

    def test_cls_query_in_subclassed_docs(self):

        class Animal(Document):
            name = StringField()

            meta = {
                'allow_inheritance': True
            }

        class Dog(Animal):
            pass

        class Cat(Animal):
            pass

        self.assertEqual(Animal.objects(name='Charlie')._query, {
            'name': 'Charlie',
            '_cls': { '$in': ('Animal', 'Animal.Dog', 'Animal.Cat') }
        })
        self.assertEqual(Dog.objects(name='Charlie')._query, {
            'name': 'Charlie',
            '_cls': 'Animal.Dog'
        })
        self.assertEqual(Cat.objects(name='Charlie')._query, {
            'name': 'Charlie',
            '_cls': 'Animal.Cat'
        })


if __name__ == '__main__':
    unittest.main()
