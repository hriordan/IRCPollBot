#! /usr/bin/env python
"""
IRC Vote/poll Bot.
An HRio Production.
"""

import irc.bot
import irc.strings
import shlex
from BotExceptions import (BadVoteOption,
                           BadPollIDValue,
                           HostAlreadyVoted)

CMD_VOTE = 'vote'
CMD_CREATEPOLL = 'createpoll'
CMD_POLLINFO = 'pollinfo'
CMD_LIST = 'list'
CMD_HELP = 'help'

helpStrings = {
    CMD_HELP: "Help is a help command that helps get you help :).",
    CMD_CREATEPOLL: "Creates a poll. args format: <pollID> <question> <answers>(1+) "
                    "PollID is a shortkey to your poll. Make it easy to type. Multiword questions and "
                    "answers must be quoted. Ex: createpoll pets 'who's better?' dogs cats 'cat dogs'",
    CMD_POLLINFO: "Print the stats of an existing poll. args format: <pollID>. Ex: pollinfo pets",
    CMD_VOTE: "Vote in a poll. Args format: <pollID> <answernumber>. Ex: vote pets 1",
    CMD_LIST: "List existing polls by pollID and question. No args."
}

defaultHelp = ("PollBot here! Commands are list, createpoll, vote, and pollinfo. "
               "Do .votebot help <command> for more info.")


class Poll(object):
    # TODO: pull from config
    pollIDMaxLen = 10

    # Answer should be list of strings
    def __init__(self, question, pollID, creator, answers=[]):
        # TODO: associate poll with channel
        self.question = question
        self.pollID = pollID
        self.creator = creator
        # voter hostnames saved here to track who voted
        self.alreadyVotedHosts = set()
        self.answers = {}
        for num, answer in enumerate(answers, start=1):
            self.answers[num] = AnswerOption(answer, num)

    def addAnswer(self, answer):
        """Add an answer to an existing poll"""
        pass

    def voteForAnswer(self, answerEnum, voterHost):
        print(voterHost)
        if voterHost in self.alreadyVotedHosts:
            raise HostAlreadyVoted

        answer = self.answers.get(answerEnum)
        if not answer:
            raise BadVoteOption
        answer.count += 1
        self.alreadyVotedHosts.add(voterHost)
        return answer

    def closePoll(self):
        """close a poll down. Don't delete contents."""
        pass


class AnswerOption(object):
    def __init__(self, answer, enumeration, count=0):
        self.answer = answer
        self.enumeration = enumeration
        self.count = count


class VoteBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, server, port=6667, nickname="VoteBot"):
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.polls = {}
        # TODO: save and load polls to db.

    def on_nicknameinuse(self, conn, event):
        conn.nick(conn.get_nickname() + "_")

    def on_welcome(self, conn, event):
        # todo: make this listen on all channels?
        conn.join(self.channel)

    def on_join(self, conn, event):
        conn.notice(event.target, "Hi I'm a poll bot! Do .votebot help to find out about me.")

    def on_privmsg(self, conn, event):
        conn.privmsg(event.source.nick, "No private chat at the moment")

    def on_pubmsg(self, conn, event):
        # prefix should be in ".botname cmd" format
        arg = event.arguments[0].split(" ", 1)
        if len(arg) > 1 and arg[0].lower() == ('.%s' % self._nickname).lower():
            self.do_command(event, arg[1].strip())
        return

    def do_command(self, event, cmdInput):
        """parse initial command input and pass to handlers"""
        target = event.target
        conn = self.connection

        inputs = cmdInput.split(' ', 1)
        cmd = inputs[0]
        if len(inputs) < 2:
            cmdArgs = None
        else:
            cmdArgs = inputs[1]

        # TODO: move this to dispatch table.
        if cmd == "createpoll":
            self.handleCreatePoll(event, cmdArgs)
        elif cmd == "pollinfo":
            self.handlePollInfo(event, cmdArgs)
        elif cmd == "vote":
            self.handleVote(event, cmdArgs)
        elif cmd == "list":
            self.handleList(event, cmdArgs)
        elif cmd == "help":
            self.handleHelp(event, cmdArgs)
        else:
            conn.notice(target, "Not understood: " + cmd)

    # command handlers

    def handleVote(self, event, cmdArgs):
        conn = self.connection
        target = event.target
        # source is in form "nick!unixuser@hostname"
        voterHost = event.source.split('!', 1)[1].split('@', 1)[1]
        if not cmdArgs:
            conn.notice(target, "No arguments supplied for vote cmd. Should <pollid> <answerNumber>")
            return
        try:
            pollID, voteAnswer = self.parseVoteArgs(cmdArgs)
        except ValueError:
            conn.notice(target, "Not enough arguments supplied for vote cmd. Should be <pollid> <answerNumber>")
            return
        except BadVoteOption:
            conn.notice(target, "Vote option must be an integer")
            return

        poll = self.polls.get(pollID)
        if not poll:
            conn.notice(target, "No such poll: %s" % pollID)
            return
        try:
            answer = poll.voteForAnswer(voteAnswer, voterHost)
        except BadVoteOption:
            conn.notice(target, "no such option %d for poll %s" % (voteAnswer, pollID))
            return
        except HostAlreadyVoted:
            conn.notice(target, "user %s, you have already voted in this poll." % event.source)
            return

        conn.notice(target, "Successful Vote. Option %d: '%s' now has %d votes." % (voteAnswer, answer.answer, answer.count))

    def handleCreatePoll(self, event, cmdArgs):
        nick = event.source.nick
        target = event.target
        conn = self.connection
        argsError = ("Not enough arguments supplied for createpoll cmd. Needs at least one answer supplied."
                     "multi-word answers/questions must be in quotes"
                     "Ex: .votebot createpoll bore 'who is?' ann? 'could it be me?'")

        if not cmdArgs:
            conn.notice(target, argsError)
            return

        try:
            pollID, question, answers = self.parseCreatePollArgs(cmdArgs)
        except ValueError:
            conn.notice(target, argsError)
            return
        except BadPollIDValue as err:
            conn.notice(target, "Invalid Poll ID %s. Must be %s chars or fewer and not already in use" %
                                (err.args[0], Poll.pollIDMaxLen))
            return

        newPoll = Poll(question=question,
                       pollID=pollID,
                       creator=nick,
                       answers=answers)

        self.polls[pollID] = newPoll
        conn.notice(target, "I created a poll with ID %s" % pollID)
        self.displayPollInfo(target, pollID)

    def handlePollInfo(self, event, cmdArgs):
        conn = self.connection
        target = event.target
        if not cmdArgs:
            conn.notice(target, "No arguments supplied for pollinfo cmd. Need a pollID")
            return
        pollID = cmdArgs.split()[0]
        self.displayPollInfo(target, pollID)

    def displayPollInfo(self, target, pollID):
        """msg channel/nick a given poll's info."""
        conn = self.connection
        try:
            poll = self.polls[pollID]
        except KeyError:
            conn.notice(target, "No such PollID %s" % pollID)
            return
        conn.notice(target,
                    "Poll ID: %(pollID)s - '%(question)s'. Options: " % {'pollID': pollID, 'question': poll.question})
        # get answers from poll
        for enum, answer in sorted(poll.answers.items(), key=lambda x: x[0]):
            conn.notice(target, " - %(enum)s: '%(answer)s', %(votes)s votes" % {'enum': enum,
                                                                                'answer': answer.answer,
                                                                                'votes': answer.count})

    def handleHelp(self, event, cmdArgs):
        target = event.target
        conn = self.connection
        if not cmdArgs:
            conn.notice(target, defaultHelp)
            return
        parsedArg = shlex.split(cmdArgs)[0]
        if parsedArg not in helpStrings.keys():
            conn.notice(target, "No such command.")
            return
        helpMessage = helpStrings[parsedArg]
        conn.notice(target, helpMessage)

    def handleList(self, event, cmdArgs):
        """list all available polls by ID to a given channel"""
        target = event.target
        conn = self.connection
        if len(self.polls) == 0:
            conn.notice(target, "No open polls.")
            return
        conn.notice(target, "Open Polls:")
        for pollID in self.polls.keys():
            conn.notice(target, "PollID %s: '%s'," % (pollID, self.polls[pollID].question))

    # Parsing helpers

    def parseCreatePollArgs(self, cmdArgs):
        """Poll args should come in form [pollID] [question] [options](variable #). Question/answers
           should be quoted in they are multi-word: Example: time "What time is it?" 3pm "4 o clock" """
        parsedArgs = shlex.split(cmdArgs)
        if len(parsedArgs) < 3:
            raise ValueError
        pollID = parsedArgs[0]
        if len(pollID) > Poll.pollIDMaxLen or pollID in self.polls.keys():
            raise BadPollIDValue(pollID)
        question, answers = (parsedArgs[1], parsedArgs[2:])
        return (pollID, question, answers)

    @staticmethod
    def parseVoteArgs(voteArgs):
        """should be in form <pollID> <answerEnum>"""
        parsedArgs = voteArgs.split()
        if len(parsedArgs) < 2:
            print("Not enough args for vote cmd")
            raise ValueError
        pollID = parsedArgs[0]
        try:
            ansEnum = int(parsedArgs[1])
        except ValueError:
            raise BadVoteOption
        return (pollID, int(ansEnum))


def main():
    # TODO: pull most info here from config file
    debug = False # TODO: get from cmdline arg
    import sys
    if len(sys.argv) != 4:
        print("Usage: votebot <server[:port]> <channel>")
        sys.exit(1)
    print(sys.argv)
    sargs = sys.argv[1].split(":", 1)
    server = sargs[0]
    if len(sargs) == 2:
        try:
            port = int(sargs[1])
        except ValueError:
            print("Error: Erroneous port.")
            sys.exit(1)
    else:
        port = 6667
    channel = sys.argv[2]

    bot = VoteBot(channel, server, port)
    if not debug:
        while True:
            try:
                bot.start()
            except Exception as err:
                print("error!")
                print(err)
                print("restarting")
    else:
        bot.start()

if __name__ == "__main__":
    main()
