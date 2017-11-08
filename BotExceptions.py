"""
Custom Exception Classes for vote bot errors.
"""


class BadVoteOption(Exception):
    """No such vote option for a given poll"""
    pass
