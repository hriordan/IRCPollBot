#! /usr/bin/env python
"""
IRC Vote/poll Bot.
Someday.
An HRio Production.
"""

import re
import irc.bot
import irc.strings


class Poll(object):
    # answers should be list of questions
    def __init__(self, question, pollID, creator, answers=[]):
        self.question = question
        self.pollID = pollID
        self.creator = creator
        self.answers = {}  # TODO: use OrderedDict?
        for num, answer in enumerate(answers, start=1):
            self.answers[num] = AnswerOption(answer, num)

    def addAnswer(self, answer):
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

    def on_nicknameinuse(self, conn, event):
        conn.nick(conn.get_nickname() + "_")

    def on_welcome(self, conn, event):
        conn.join(self.channel)

    def on_privmsg(self, conn, event):
        # self.do_command(event, event.arguments[0])
        conn.privmsg(event.source.nick, "No private chat at the moment")

    def on_pubmsg(self, conn, event):
        # prefix should be in ".botname cmd" format
        arg = event.arguments[0].split(" ", 1)
        if len(arg) > 1 and arg[0] == ('.%s' % self._nickname):
            self.do_command(event, arg[1].strip())
        return

    def do_command(self, event, cmdInput):
        nick = event.source.nick
        target = event.target
        conn = self.connection

        # ideally in form cmd args
        inputs = cmdInput.split(' ', 1)
        cmd = inputs[0]

        # TODO: move this to dispatch table structure
        if cmd == "createpoll":
            if len(inputs) < 2:
                conn.notice(target, "No arguments supplied for createpoll cmd")
                return
            try:
                question, answers = self.parseCreatePollArgs(inputs[1])
            except ValueError:
                conn.notice(target, "Not arguments supplied for createpoll cmd. Needs at least one answer supplied."
                                    "Both question and answers must be in double quotes")
                return
            pollID = self.handleCreatePoll(question, answers, nick)
            # args format: question (string) variable number of options
            conn.notice(target, "I created a poll with ID %s" % pollID)
            self.displayPoll(target, pollID)

        elif cmd == "pollinfo":
            if len(inputs) < 2:
                conn.notice(target, "No arguments supplied for pollinfo cmd")
                return
            pollID = self.parsePollInfoArgs(inputs[1])
            self.displayPoll(target, pollID)

        elif cmd == "help":
            conn.notice(target, "The help is not here yet.")

        else:
            conn.notice(target, "Not understood: " + cmd)

    def handleCreatePoll(self, question, answers, creator):
        """register a poll to the polls dict."""
        # make an "ID" for the poll. creator nick + something else?
        pollID = creator + str(len(self.polls))  # sure why not
        newPoll = Poll(question, pollID, creator, answers)
        self.polls[pollID] = newPoll
        print("created poll %s" % pollID)
        return pollID

    def displayPoll(self, target, pollID):
        """msg channel/nick a given poll's info."""
        conn = self.connection

        try:
            poll = self.polls[pollID]
        except KeyError:
            conn.notice(target, "No such PollID %s" % pollID)
            return

        response = "Poll ID: %(pollID)s - '%(question)s'. Options: " % {'pollID': pollID, 'question': poll.question}
        # get answers from poll
        for enum, answer in sorted(poll.answers.items(), key=lambda x: x[0]):
            response += " - %(enum)s: '%(answer)s', %(votes)s votes" % {'enum': enum,
                                                                        'answer': answer.answer,
                                                                        'votes': answer.count}

        conn.notice(target, response)

    def listPolls(self, channel):
        """list all available polls to a given channel"""
        pass

    def voteInPoll(self, pollID, answer):
        """vote for answer in poll"""
        pass

    @staticmethod
    def parsePollInfoArgs(infoArgs):
        return infoArgs.split()[0]

    @staticmethod
    def parseCreatePollArgs(pollArgs):
        """
        Poll args should come in form [question] [options](variable #). They need to be quoted.
        Double quotes required, for now. Example: "What time is it?" "3pm" "4pm" "midnight"
        """
        stringRegex = '"([^"]*)"'
        parsedArgs = re.findall(stringRegex, pollArgs)
        if len(parsedArgs) < 2:
            print("not enough args for createpoll cmd")  # switch to log
            raise ValueError
        question, answers = (parsedArgs[0], parsedArgs[1:])
        return (question, answers)


def main():
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
    while True:
        try:
            bot.start()
        except Exception as err:
            print("error!")
            print(err)
            print("restarting")

if __name__ == "__main__":
    main()
