"""Implementation of Direct Acyclic Graphs."""

from __future__ import absolute_import, division, print_function

from e3.error import E3Error


class DAGError(E3Error):
    pass


class DAGIterator(object):

    NOT_VISITED = 0
    BUSY = 1
    VISITED = 2

    def __init__(self, dag, enable_busy_state=False):
        """Initialize DAG iterator.

        :param dag: the dag on which iteration is done
        :type dag: DAG
        :param enable_busy_state: used to implement topological parallel
            iteration. When False, a vertex has only 2 possible states: VISITED
            or NOT_VISITED. When true, calling the next() function on the
            iteratior puts the element in 'BUSY' state. It will only be moved
            to 'Visited' once calling the 'leave()' method.
        :type enable_busy_state: bool
        """
        self.dag = dag
        self.non_visited = set(self.dag.vertex_data.keys())
        self.states = {k: self.NOT_VISITED
                       for k in self.dag.vertex_data.keys()}
        self.enable_busy_state = enable_busy_state

        # Compute number of non visited predecessors for each node.
        # Doing this computation in advance enable faster
        # iteration overall (simplify conditions in next_element)
        self.pred_number = {
            k: len(v) for k, v in self.dag.vertex_predecessors_items()}

    def __iter__(self):
        return self

    def next(self):
        """Retrieve next_element with with_predecessors=False.

        The intermediate function is needed in Python 3.x

        :rtype: (None, None) | (str, T)
        """
        return self.next_element()[0:2]

    def next_element(self):
        """Retrieve next element in topological order.

        :return: a tuple id, data, predecessors. (None, None, None) is
            returned if no element is available).
        :rtype: (str, T, list[str]) | (None, None, None)
        """
        if not self.non_visited:
            raise StopIteration

        # Retrieve the first vertex for which all the predecessors have been
        # visited
        result = next(
            (k for k in self.non_visited if self.pred_number[k] == 0), None)

        if result is None:
            if not self.enable_busy_state:
                raise DAGError('cycle detected')
            # No vertex is ready to be visited
            return None, None, None

        # Remove the vertex from the "non_visited_list" and when
        # enable_busy_state, mark the vertex as BUSY, mark it VISITED
        # otherwise.
        if self.enable_busy_state:
            self.states[result] = self.BUSY
        else:
            self.states[result] = self.VISITED
            # Update the number of non visited predecessors
            for k in self.dag.get_successors(result):
                self.pred_number[k] -= 1

        self.non_visited.discard(result)

        return (result,
                self.dag.vertex_data[result],
                self.dag.get_predecessors(result))

    def leave(self, vertex_id):
        """Switch element from BUSY to VISITED state.

        :param vertex_id: the vertex to leave
        :type vertex_id: str
        """
        assert self.states[vertex_id] == self.BUSY
        self.states[vertex_id] = self.VISITED
        # Update the number of non visited predecessors
        for k in self.dag.get_successors(vertex_id):
            self.pred_number[k] -= 1


class DAG(object):
    """Represent a Directed Acyclic Graph.

    :ivar vertex_data: a dictionary containing all vertex data
        indexed by vertex id
    :vartype vertex_data: dict
    :ivar tags: a dictionary containing "tags" associated with
        a vertex data, indexed by vertex id
    """

    def __init__(self):
        """Initialize a DAG."""
        self.vertex_data = {}
        self.tags = {}

        self.__vertex_predecessors = {}
        self.__vertex_successors = {}
        self.__has_cycle = None

    @property
    def vertex_predecessors(self):
        """Return predecessors.

        Meant only for backward compatibility. Use vertex_predecessors_items.

        :return: a dictionary containing the list of predecessors for each
            vertex, indexed by vertex id
        :rtype: dict
        """
        # We're doing a copy of the __vertex_predecessors dictionary
        # to avoid external modifications
        return dict(self.__vertex_predecessors)

    def vertex_predecessors_items(self):
        """Return predecessors.

        :return: a list of (vertex id, predecessors)
        :rtype: dict
        """
        return self.__vertex_predecessors.iteritems()

    def get_predecessors(self, vertex_id):
        """Get set of predecessors for a given vertex."""
        return self.__vertex_predecessors.get(vertex_id, frozenset())

    def set_predecessors(self, vertex_id, predecessors):
        """Set predecessors for a given vertex.

        Invalidate the global dictionary of vertex successors.
        """
        self.__vertex_predecessors[vertex_id] = predecessors
        # Reset successors and cycle check results which are now invalid
        self.__vertex_successors = {}
        self.__has_cycle = None

    def get_successors(self, vertex_id):
        """Get set of successors for a given vertex.

        If the global dictionary of vertex successors has not been
        computed or if it has been invalidated then recompute it.
        """
        if self.__vertex_successors == {}:
            self.__vertex_successors = {
                k: set() for k in self.__vertex_predecessors}
            for k, v in self.__vertex_predecessors.iteritems():
                for el in v:
                    self.__vertex_successors[el].add(k)
            # Use frozenset to prevent the modification of successors
            for k, v in self.__vertex_successors.iteritems():
                self.__vertex_successors[k] = frozenset(v)

        return self.__vertex_successors.get(vertex_id, frozenset())

    def add_tag(self, vertex_id, data):
        """Tag a vertex.

        :param vertex_id: ID of the vertex to tag
        :param data: tag content
        """
        self.tags[vertex_id] = data

    def get_tag(self, vertex_id):
        """Retrieve a tag associated with a vertex.

        :param vertex_id: ID of the vertex
        :return: tag content
        """
        return self.tags.get(vertex_id)

    def get_context(self, vertex_id, max_distance=None, max_element=None,
                    reverse_order=False):
        r"""Get tag context.

        Returns the list of predecessors tags along with their vertex id and
        the distance between the given vertex and the tag. On each predecessors
        branch the first tag in returned. So for the following graph::


                A*
               / \
              B   C*
             / \   \
            D   E*  F

        where each node with a * are tagged

        get_context(D) will return (2, A, <tag A>)
        get_context(E) will return (0, E, <tag E>)
        get_context(F) will return (1, C, <tag C>)

        When using reverse_order=True, get_context will follow successors
        instead of predecessors.

        get_context(B, reverse_order=True) will return (1, E, <tag E>)

        :param vertex_id: ID of the vertex
        :param max_distance: do not return resultsh having a distance higher
            than ``max_distance``
        :type max_distance: int | None
        :param max_element: return only up-to ``max_element`` elements
        :type max_element: int | None
        :param reverse_order: when True follow successors instead of
            predecessors
        :type reverse_order: bool
        :return: a list of tuple (distance:int, tagged vertex id, tag content)
        :rtype: list[tuple]
        """
        self.check()

        def get_next(vid):
            """Get successors or predecessors.

            :param vid: vertex id
            """
            if reverse_order:
                result = self.get_successors(vid)
            else:
                result = self.get_predecessors(vid)
            return result

        visited = set()
        tags = []
        distance = 0
        node_tag = self.get_tag(vertex_id)
        if node_tag is not None:
            tags.append((distance, vertex_id, node_tag))
            return tags

        closure = get_next(vertex_id)
        closure_len = len(closure)

        while True:
            distance += 1
            if max_distance is not None and distance > max_distance:
                return tags
            for n in closure - visited:
                visited.add(n)

                n_tag = self.get_tag(n)
                if n_tag is not None:
                    tags.append((distance, n, n_tag))

                    if max_element is not None and len(tags) == max_element:
                        return tags
                else:
                    # Search tag in vertex predecessors
                    closure |= get_next(n)

            if len(closure) == closure_len:
                break
            closure_len = len(closure)
        return tags

    def add_vertex(self, vertex_id, data=None, predecessors=None):
        """Add a new vertex into the DAG.

        :param vertex_id: the name of the vertex
        :type vertex_id: collections.Hashable
        :param data: data for the vertex.
        :type data: object
        :param predecessors: list of predecessors (vertex ids) or None
        :type predecessors: list[str] | None
        :raise: DAGError if cycle is detected or else vertex already exist
        """
        if vertex_id in self.vertex_data:
            raise DAGError(message="vertex %s already exist" % vertex_id,
                           origin="DAG.add_vertex")
        self.update_vertex(vertex_id, data, predecessors)

    def update_vertex(self, vertex_id, data=None, predecessors=None,
                      enable_checks=True):
        """Update a vertex into the DAG.

        :param vertex_id: the name of the vertex
        :type vertex_id: collections.Hashable
        :param data: data for the vertex. If None and vertex already exist
            then data value is preserved
        :type data: object
        :param predecessors: list of predecessors (vertex ids) or None. If
            vertex already exists predecessors are added to the original
            predecessors
        :type predecessors: list[str] | None
        :param enable_checks: if False check that all predecessors exists and
            that no cycle is introduce is not perform (for performance)
        :type enable_checks: bool
        :raise: DAGError if cycle is detected
        """
        if predecessors is None:
            predecessors = frozenset()
        else:
            predecessors = frozenset(predecessors)

        if enable_checks:
            non_existing_predecessors = [k for k in predecessors
                                         if k not in self.vertex_data]
            if non_existing_predecessors:
                raise DAGError(
                    message='predecessor on non existing vertices %s'
                    % ", ".join(non_existing_predecessors),
                    origin="DAG.update_vertex")

        if vertex_id not in self.vertex_data:
            self.set_predecessors(vertex_id, predecessors)
            self.vertex_data[vertex_id] = data
        else:
            previous_predecessors = self.get_predecessors(vertex_id)
            self.set_predecessors(
                vertex_id, previous_predecessors | predecessors)

            if enable_checks:
                # Will raise DAGError if a cycle is created
                try:
                    self.get_closure(vertex_id)
                except DAGError:
                    self.set_predecessors(vertex_id, previous_predecessors)
                    raise DAGError(
                        message='cannot update vertex (%s create a cycle)'
                        % vertex_id,
                        origin='DAG.update_vertex')

            if data is not None:
                self.vertex_data[vertex_id] = data

        if not enable_checks:
            # DAG modified without cycle checks, discard cached result
            self.__has_cycle = None

    def check(self):
        """Check for cycles and inexisting nodes.

        :raise: DAGError if the DAG is not valid
        """
        # Noop if check already done
        if self.__has_cycle is False:
            return
        elif self.__has_cycle:
            raise DAGError(
                message='this DAG contains at least one cycle',
                origin='DAG.check')
        # First check predecessors validity
        for node, preds in self.__vertex_predecessors.iteritems():
            if len([k for k in preds if k not in self.vertex_data]) > 0:
                self.__has_cycle = True
                raise DAGError(
                    message='invalid nodes in predecessors of %s' % node,
                    origin='DAG.check')
        # raise DAGError if cycle
        try:
            for _ in DAGIterator(self):
                pass
        except DAGError:
            self.__has_cycle = True
            raise
        else:
            self.__has_cycle = False

    def get_closure(self, vertex_id):
        """Retrieve closure of predecessors for a vertex.

        :param vertex_id: the vertex to inspect
        :type vertex_id: collections.Hashable
        :return: a set of vertex_id
        :rtype: set(collections.Hashable)
        """
        self.check()
        visited = set()
        closure = self.get_predecessors(vertex_id)
        closure_len = len(closure)

        while True:
            for n in closure - visited:
                visited.add(n)

                closure |= self.get_predecessors(n)

            if len(closure) == closure_len:
                break
            closure_len = len(closure)
        return closure

    def reverse_graph(self):
        """Compute the reverse DAG.

        :return: the reverse DAG (edge inverted)
        :rtype: DAG
        """
        result = DAG()

        # Copy the tags to the reverse DAG
        result.tags = self.tags

        # Note that we don't need to enable checks during this operation
        # as the reverse graph of a DAG is still a DAG (no cycles).
        for node, predecessors in self.__vertex_predecessors.iteritems():
            result.update_vertex(node,
                                 data=self.vertex_data[node],
                                 enable_checks=False)
            for p in predecessors:
                result.update_vertex(p,
                                     predecessors=[node],
                                     enable_checks=False)
        try:
            result.check()
        except DAGError:
            # Check detected
            self.__has_cycle = True
            raise
        else:
            # No cycle in the DAG
            self.__has_cycle = False
        return result

    def __iter__(self):
        return DAGIterator(self)

    def __contains__(self, vertex_id):
        """Check if a vertex is present in the DAG."""
        return vertex_id in self.vertex_data

    def __getitem__(self, vertex_id):
        """Get data associated with a vertex."""
        return self.vertex_data[vertex_id]

    def __or__(self, other):
        """Merge two dags."""
        assert isinstance(other, DAG)

        result = DAG()

        # First add vertices and then update predecessors. The two step
        # procedure is needed because predecessors should exist.
        for nid in self.vertex_data:
            result.add_vertex(nid)

        for nid in other.vertex_data:
            result.update_vertex(nid)

        # Update predecessors
        for nid in self.vertex_data:
            result.update_vertex(
                nid,
                self.vertex_data[nid],
                self.get_predecessors(nid))

        for nid in other.vertex_data:
            result.update_vertex(
                nid,
                other.vertex_data[nid],
                other.get_predecessors(nid))

        # Make sure that no cycle are created the merged DAG.
        result.check()
        return result

    def as_dot(self):
        """Return a Graphviz graph representation of the graph.

        :return: the dot source file
        :rtype: str
        """
        self.check()
        result = ['digraph G {', 'rankdir="LR";']
        for vertex in self.vertex_data:
            result.append('"%s"' % vertex)
        for vertex, predecessors in self.__vertex_predecessors.iteritems():
            for predecessor in predecessors:
                result.append('"%s" -> "%s"' % (vertex, predecessor))
        result.append("}")
        return "\n".join(result)

    def __len__(self):
        return len(self.vertex_data)

    def __str__(self):
        self.check()
        result = []
        for vertex, predecessors in self.__vertex_predecessors.iteritems():
            if predecessors:
                result.append('%s -> %s' % (vertex, ', '.join(predecessors)))
            else:
                result.append('%s -> (none)' % vertex)
        return '\n'.join(result)
