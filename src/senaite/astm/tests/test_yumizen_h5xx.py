# -*- coding: utf-8 -*-
# flake8: noqa

from unittest.mock import MagicMock
from unittest.mock import Mock

from senaite.astm import codec
from senaite.astm.constants import ACK
from senaite.astm.constants import ENQ
from senaite.astm.instruments import horiba_yumizen_h5xx
from senaite.astm.protocol import ASTMProtocol
from senaite.astm.tests.base import ASTMTestBase
from senaite.astm.wrapper import Wrapper


class ASTMProtocolTest(ASTMTestBase):
    """Test ASTM Communication Protocol
    """

    async def asyncSetUp(self):
        self.protocol = ASTMProtocol()

        self.lines = [
            b'\x021H|\\^&|||H500^910YOXH02815^2.2.2.2b|||||||P|LIS2-A2|20230324135102\r\x03AA\r\n',
            b'\x022P|1|||||||||||||||||||||||||||||||||||\r\x0333\r\n',
            b'\x023O|1|CL-BL-23-0003||^^^DIF|R|20230324134947|||||||||BLOOD||||||||||F|||||\r\x03D8\r\n',
            b'\x024C|1|I|NON_COMPLIANT_DATA^WBC^NOISE\\NON_COMPLIANT_DATA^WBC^ABNORMAL_DIFFERENTI|I\r\x03A3\r\n',
            b'\x025M|1|HISTOGRAM|RBC/PLT|RbcAlongRes|FLOATLE-stream/deflate:base64^Y2AAgW5nMMXg6gIkHEAsAA==|FLOATLE-stream/deflate:base64^3dR/aJR1HMDxb/5KOrWl47L8tcPfdUfO1E1R93y/n/NH5daprLw2yx+XqYWnTlPOqY9rO5dL3DBK2hGDcCtlIIeIBodGKUeUDI8IkdwUEXcEFdsqZITvZ95w9\x17D7\r\n',
            b'\x026Y9a/3Xw5p7nue+9vt/7PsejlPOqkZ43tcCvlGUptdgolSR35rri2h4JeWoKQh6X5Y4HLI6tRHszxy1WONLBuUvXVY3WiXafThcWaMZoca/R4UiZLgpXaMbrSOowY2K6Ke8o45p1qv4UY89q5mJ8i/aFLvOd6zqYTPO9Dh31dvPdfiaYHGTwTTjyuImkRpiod6RhLhO7mmOa8iaaeO1Uw7wmaaabVP0s09o5x7AG09Uoxvktr\x173B\r\n',
            b'\x027uASw3qMx1VsfKGgyU+sNKzNFIXXYW/EDmOXYe/ALsex+awCq5LPo3jVjKnBPMi4Q7h1jD2M/RHjj+B/wnpizPEpa2pgns9Y11HmamJtXzDfcdbXzJwnsOPYJ7FPYZ/G/hI7gX0W+yvsr7HP9+x/1Pst9nfYF7FbsC9h/4D9I/Zl7CvYP2G3Yl/HvoF9E/sWdhr7Z+xfsH/D7sDuwv4D+zZ2N/ZffEeJK/iIsM9SV9VfUvUDx\x17F6\r\n',
            b'\x020B0fKOy5xK4+Kq2dg8Xjeox775KmvCGSLhwqvtAw4V5IvDZLuhqfkPzEcOG+SKI9W5z/jLifFO6RJM1T2E9jj8IejT0Geyz2OOwcbA/2eOwJ2BOxJ2FPxp6CPRX7Gexnsb3YPuznsKdh52JPx34eewb2TOxZ2HnY+dizsedgz8Wehz0fuwDbwtbYBluw/dgLsBdiL8Z+AftF7Jewl2AXYhdhv4wdwF6KvQx7OXYx9ivYr2Kvw\x17ED\r\n',
            b'\x021A5iv4Zdgl2KvRL7dew3sFdjr8Feix3CfhN7HfZb2OuxN2BvxH4b+x3sTdhh7M3YW7C3Ypdhb8Pejv0u9g7sndgR7F3Y5di7sfdg7+XYlvT3Nuf7xHdjH9cqJHy7gjnfk3hWJfNWStekKuaukvx5UeaPSmT5ftawXxIbqllHtSj7fdZyoPcZ8B9edsG9nGeJk/OcsanhX3aO2hyL58c0ClA1fU4tNID/+RQqpQ/oGF2ibhrJb\x1737\r\n',
            b'\x0225pBxVTO7/yYmjn+hq5QB+cDeRYO9ytrjF+dm8xxrl/Zs53nI9f8XBN/z/PS5lhpzufSTD7z8T6ea6P4LItjHPt3vGt0kc7gN9IRjqO8b6USWkS5NJaGOXtOtzJrvkAnqZFi9CEdoEramWk9raIVFCA/WeSlCZRD2TTE3N2bP9mjX6mt5/mr1Gk6kdk/pwaqzezpZlqV2eNAZr/7lkNZ+u69eJB671vf87bMPf3nPe49th8gq\x1729\r\n',
            b'\x0230/qIev7H71f/9fX33/nHQ==\r\x03C0\r\n',
            b'\x024M|2|HISTOGRAM|RBC/PLT|PltAlongRes|FLOATLE-stream/deflate:base64^Y2AAAQ4nMMXQA6IdgMghPS3IYee8Q46rPpo4QuQa7EFyAA==|FLOATLE-stream/deflate:base64^3ZR/TJR1HMdPuBlU1DFpjBxNnKJZI2JJJsXzfT83YwwaOhpDhw2TJWOdiymSMfBEUwISglQMilMQ0aDOPOVHQGAogkFChAR1E\x175D\r\n',
            b'\x025MQPg8LQEOqs3g88f5AzW/3ps3vtubvvj8/7Xt/nPhqNcjnI0zdNOu9GwTdkATQaE7mKmTHlux16g3WJv83loH/dyi5/vfkByVPvLTl0rJFGordIQ4mpUnhArtSoK5H8uqqkkoJmyd1glTJ8xyRlfUWUg4ht1IllXm6iP8tD5N54VLwY4SOc6laKc4v1Iik1SDw9FirGQiNEcXmU2OBuEG7JcaJtMJHju8TC8L2ckya6qjI4L\x1776\r\n',
            b'\x0261tke+Rwbp4I3mPi/EKhHSnmmlJRHXKS606LbZYKrq0WXm5nRWrQeTGU2CT05haR39cmbC6XRXhAt7Bs7xHOJf3CYB0SjbpR4am/KpLjrgvrsUnh12Xj3hq8kW+H4nItOlrnQjviAB/tfdjg7oQM3wdRHeKMkeh5cEt+CAG5rthmcUNh83y0DbpDcXht3kIMLFmETj9PXAxZipqNy2COfxwFaV44kO+NlFM+SGh4Cpu7fRE5t\x171C\r\n',
            b'\x027gKh9n543vU5PPOYBL7wSKgezptWwT4hABP7AnHlSBC6z7yAlqYQ1FnXwDIeiqK5YTj0cDjSvdYhSY5AbNhLiIqJRFjSywjMisKzRa/gicpoeLTEwKXvVdwzsRlTjrEYdd+Cnifj0LoqHvVrt6PMkIATOxORt38HGtqN3H8nKoeTWWMXSm27WWcPTLq9rJWCrEVvsV4q3lyRxprpeD34bdbdh5jIDNbOxPqt77B+FlanZDPDu\x17DD\r\n',
            b'\x0205Dz9jPHASw3H2SWHCytP8Q872F+Zy4z5cFp9H3m+mD6mZtyPExvR5ivgO4KmfEo/RUx5zE6LGbW4/R4gnk/pMsSZi6lz4+Y+2M6NSPj+El6/QTJ1afo1oKtrafp9ww2DZTRcTnWTVXQ86cIdqqi62pIHjX0/Rl8ltfSeR0WB56l98/hur6e7s/h3tjz9N+Am7sv8AwaMZbTxHO4iL6SL3gWzfi6toXn8SWdXaKzVjpro7Ov6\x17BB\r\n',
            b'\x021Kydzjro7DKdddLZN3TWRWfddPYtnX1HZ1Y666GzXjr7ns766Kyfzn6gswE6G6SzITobprMrdPYjnY3Q2Sid/URnP0//R6ccf6GzcTq7RmfX6exXOpugsxt0NklnU3T2G539Tmc2OrtJZ3/Q2Z8c18gN7Rq5fu0cuc46R67ZaCdXDtvJZQZ72TJuL5vjtXKpTav2iP96GaW/o/QRIWb6jInUkl6l52Cm5wgSSYwkU+1BZlJLL\x17CB\r\n',
            b'\x022pFOtScpTCq9ibmUbEoPu/8f0N3y2WEWWhWNyqS6r7L/MOlV6VTrK1xQ8yiUq5hVilVMKjkqmbNIUTGqvKb+ZoXVKkLFW2XBLHQqmtvQK25P7R0w/Q+M/4K4A5q7lFuf9buHvwA=\r\x03E1\r\n',
            b'\x023M|3|MATRIX|LMNE|LMNEResAbs|FLOATLE-stream/deflate:base64^Y2AAggf/XRjgtIMDiAkA|FLOATLE-stream/deflate:base64^7Z131GRVte2POUtGQEIRGklNRjIcqA8QyUhQgpR6r6JcUAmiqHjItOQgNLmAhiaHJiPQRRLRJiMoyVIQEUW8Ini9avfbvzln9ddvjPfHG2+MN969b5weY3fVV3XOPnuvNddc\x17FB\r\n',
            b'\x024a++99q6qKv+Gs8aqOV/1r6mr+tTNqnrhsar++FjVbDlWDVYrZeVyDe8XLK9LlfKh8r58P1i9lI+W61Yqn81TykalLFfK0qV8pBTuW7NcU5eyWLnu7aW8q9S9bilr+N7BQuWz9cvf5Tn1MmN+drd8tnZ5XaK8frhcU14HE8v7ldOWbp7Fs3m/SikrlO9WLH//Z7eqPlXeb1bef6yUrUr5j25Vl/YNPua2DTbI/Su6XQPaXq6r\x176D\r\n',
            b'\x025/tatBqUNg9L2ZvHyWp5dr+m+NaV9Tbm3XtptpV98R98Hi5T3lFVLWat8tnF5LX2tPli+K5819HHe8jdyKnVW65XPS5ubudzm6j2lIOd1LIvB8qW8v3xWZFB1ymcTyt/l82rR8rquP0dW9Lvmnsi6KX2ueU/bl7WcBtuWMn8ppS3Vuu4bddebRI5cO195Lbqseb+C24IsqiVLnR+PLBYon/3Tnw3oR9FHXdpTl7428+X78tlg\x176E\r\n',
            b'\x026QvT5UeuX9g2W9nfN6qm36KhBV5ukr+hleWOh/oDbM/iA29cUrFXblfLu8t1cloN08d48Z3nrGNmii3rJcZ00RW81zyxtGxQZD5aznpol3fYKfKH/Na1b+l2Xa5u5S+HalaKblYzdqmC23tT1qQ1FB02xBzBTL2g9cU0z5nbU8/p78II+hJ0i34byjvIeWa3p66pSb1PaU6Pn+VzqDYPV5dPPbfw39w86ub60tUbvneABrL2z\x17E8\r\n',
            b'\x027lGWtG2y2LvZXlddBqa/GVuZyW8CEsLWo2622L2BbEsaXMn6lryXcz8HaroPn1WsbC4ONo3fktkpwDr43Na4Gu5T3Re7VWtHlRraJwabGPxxDXQ1tncef1+9y25tZxSbnCn9g7+hjQ7+XjBaN3pHZJ2zz4pwVjOfqHX4uOJB9Lhm5wUWLmldqbGNm13VtHnl8NM9cPfwzwXxXrR9OnCft29C6QaZqzyLGu3C2sktNWc8yE39h\x17B2\r\n',
            b'\x020o8uYC2Rz2/u1eb/13ywfHSxs2x4sHK6ZaPtWPz4WDG3kPsI53Af/wZsVnEv/N0j7quBgZJPdYBfcf8xyxF7FLe8yLmh3s0b4gvasaH1I/ou6PcLDvPYX9baWWVX4VrhbzHYiDl3f/anWMe5le2ORzcgGVo49YK9LWQ+yYdq7he+XHcUeBu8Op21lvNN/2ginIT9hbG3rUH5ijfBcbQyga+6TTt9mzqg2cRG/LO9+DSrLAb5p\x17C1\r\n',
            b'\x0211snnXDe3P6/eH/y9Jxw90Z8Jt8uH07YxzwkTPHNhtwtcwCf4oqa2zaHTZjvzX71crl89dr605Yocq/hF6W7tyATO2No6rcDJmH0pfIrPbtZ132mL7Bn+Wys2u6T128xvP07feL6wv1J801buV/Pu6GeJcOeK5lX56RXCiatZn+hQfj64V73vsCzxhcLuhu6ffPha9qOD+KF6Kftz1cn9H4ycwWaJS/geu5dNLxb5bGG/16C7\x1747\r\n',
            b'\x022jcxN+A/ZwnrGDfFNg58BJ/OaU8XPS9k25Y/mCo8XTNXvi98jPpjfnKq2LJvPF0z/Pmpdyj7QZ+SNT4SvsVHFTGBoguWFzsUna1gX9XttD+iz2tyyQyZgFZnyOVzNs+Qvt7edgk3FHCsEpxsFI3PZ/8lmOrapens/Q7HHEuY3tXkhy07xx0TLSH3Gr3zIssNG4TPZ56LGkPS9ujml6QQfSwfzawQXu5q3dA33rWI7El8s7jrq\x1767\r\n',
            b'\x023+Gc9b+cx+VnFMPOEwxKDiTMnGrdwinS4kLkRexD/zZfvVg6+4b0VjR1h6OPmH2Kv6u2uD7nKL60eGxr1cWLwjR7eaTnTVmwce5M/Xdz643n15un31sZYNb9tUTqHA3cOd+1qLIr/ynOJj+VHVw5m5s+9a/k7tR35YZOfctu5nnqks+XjR5aMv6NtC4TDl/crOJV+uvbnvCfekV6x/c3CXXOlnx+2voiTscNqFJ/NE90vaN4d\x17CA\r\n',
            b'\x024jLh5dWNFdj135LR2bGbj6A4dIp/l4u/WCxcvFv+EvDeIna4Z/p3o+sAwMlVda9nGKnzvRpHHEvZ5+E7pDRuhjvXM84oPOvEV85o34IjBu8IXC47rW1y6vn06+lC7F7Ee613C1R+xfOSnN/ezhOd3x9d/zLJQe4jx/tGVv4dXxdEbBHvcU3wRcbdi19KWegvjqSn3DD5pX1Nv7X6CTewRWQgb1LWF+yVe7ZifFP+sac7FjuAv\x176F\r\n',
            b'\x025yQ0sbmq50Ab5pZWC/fn8TD1/RcdR4Ez3LJn2Eke+N/7oA/ETqxhv6jdjkHe6LnH7wuGp9exXNfZazrrQOHEFcwE6oS2KSbG9ZY1P+YGPud/yeYmFFKtzzyeDhe3NO9i3ZL/YOBYkg47xKfnP4zYq3kOWbxubPUbSOG1ieI4YbzNzl3z+2vbH+D6NGzY0LpvR2PBdxrY4eqfy3dbxWfiEZS1v+fr3xu903D9wrDhmmegPjJax\x17E5\r\n',
            b'\x026l2KlOjyDfcEp8aOMpWrk/PeudKf4cG73GTxp3ItfXCVcMb95n/GCbGNC6psrvrNr+TaxKdqkOHuC+0s8Jj5eyL5SPL9IdMa1c7mNVWy7SqyJ79N4bzlzimxy9fDOXJHN+nn2mq5T/m6e+Ir1w28ftT/TOG3r6GQN1weXDRKLaRwU3yZMLhCdvD38mTGo5hKWjJ8jBoLLtraNqA3zWd/gUGMkbOZt4cUPRufENRuYFyT3ecMz\x176E\r\n',
            b'\x027yP89lq/iaer4sF8VE8IDO7s/8DzzF7LlieYQ+WJsfeHIYDPbrOZQVjGOpL95jYVR7Deyc/CC7rm+Wsw22MTvK/bfyXKX7142vhC7CifKjhdM3zqR8QKWSTOam/mgdY/vECd1jH/iTmFkYdepeR04roof29CyF+YYDy3lOoh5kJ1sb27XL05dxBw5WDJ2i42sGjmBn4XMAYqdVwr/LmKdVruEm5eO/taKfiZYL1X6JQ7j2djS\x17EA\r\n',
            b'\x020+8Lr6/tZGqci16XcN/kbxjHb2raYp5BMO5HFKrG5t5kTFMevEOwSSzF2Lq/Evswz1R8yHogvNGe0bLDesa7ln1YK5laLfS0U21whNldkq7mYNcO/o3k62jTR9sOYHT7XPNmG0eXHw5MbmH9krwvathV7Lm65MJ7RmGydYG4JxyrCZuYkNAbMGBL8gh3p6e3hnlUtw7qMi/BXmk9cJHy3UDh+JLvEQIrnsc8x60u+fw3LWnr9\x1738\r\n',
            b'\x021QHRFHxkH0/8dS3lfdPoxY44xgXh//vj0j1gP4AHfL3spemT+pSmY0TzeMuHqkQ3ibzc35uRHqWs124I4BmzEXyoenM+4HGwe+czr+zS/gry3c5/lVyZaVuhYNo8dwlEft5w17wXHrBZ7XMz41nzBsvaravPHwkUTw9sTjHH5mcyLKV6daLuvYkuK7/ErK4aD8W9b2jeoHcxhfiRtgGNnet6UeRSNlzc0H9Fn6XqV2ArfLxnf\x1763\r\n',
            b'\x022slg46ZPmfsWS8PbKse8d4882s7/RGGsV9w8bE+/j05bwvZoHWDN8ML+xI11MML/TZ/F7bIhYU+PW9cI38CG2l3kezUHQtk1jO0uNy0RziRkjjeIHbFcx0krB3+q2L2xZdr6AMSlZrxTehle38jORLzwJjhR/4YdnOkYc8aa4ffnEHQsFJxMia/SDf1rXvK2+L2s7rUYxfeJ52dC8ttUBcQPxG7azmfEpm14k333Az8XfaBzQ\x179A\r\n',
            b'\x023Ma4l8wXGxuc/V7WfH8wd3zHB3EJ/hdmOnyG5rBjOX9ycqDE2Y4tiA4ybNTYo3KsxykfNL+Jc/OR20fMS6d98tkvNj64a3/rO6HYN2wj9UQzK/DVtXzJ+YvGx2WsdwiJ1rm/dq//rWE+aX9jMdjUYzQeuHBtdKNjYIP4DjC1r/pYvWTP2t6zlrbhtFXOO4ne+2zgYWMrfyafOY97S3Bp9w8cvnr6um3aVOKH5p+Mp+Ybl3P5q\x1704\r\n',
            b'\x024zFglnlbcQJ+XDgch543sT4Stze1fNE8J59bWr8bFK1sv2OEgPkfzF+8Jb6+feAIOeVd4c6HY02KWYQUvbRvOea/lwDi9Go3llxrnH9ntO9K/cLHGVbXjA2FwnnDz+uZQ+YSsu8AtIwzKf2X+UOtMa4YPRzzAXAi+ree+K36mT4V3Bp/29fVXStnZ+hYXHlLu/7dSditlv1K+Ub7/dLgLmX3L8td8eG2bGHzVelJ8gK2XV8Zi\x17D8\r\n',
            b'\x025g/3HNHaveua6wQ6pa3e/Ml4Y7G1+0hzMVv6s+nR8CvzFPZtYjrJz9LyrOXOw15jGG9VXjDnFHdtYzsxFyl7R74Hx2cwFUf/p1r38Htj5RPmbOQbm8kv/68+W93vYX2qdrfSvOqy8fsHPVJ/G0j7axLoh/YZLi9wY+9IvzcGeVEppn+LQ7fL81Vwv1w8Ps89EJ/WhpZT7Bujg82OK3+p/HfP8DzpiDHC09QlWhJeD48uwmSKT\x1712\r\n',
            b'\x026XlPKYe5Tta/vk72gv92Cu4/7tdk9fdnWfekdXj7/3JhjjwOCzdKmZs9yz1fcdr4bIJ993G7aCpbwNYN/MTczLh2e6edV5VrNHRxk7ibeqPez3MCE5lqWNf5pO1hsvlTK56Of0pemyJz1UnBRf8Oc2HzNzxn0rGvG2she9rOln6t1rHJ9U/pADM4chDD5zeiK9m9vXQ72TT+Q/9fc5ubrY15jKP3qNPGjXy5lX8tJce0n/Nmg\x1783\r\n',
            b'\x0271FmDy31S34TghXiG+79ve0OuattXzLfq1w72JdSDzFQXfm5Dc0pdsNjsZ781QDab2/40L/NJ65rYqjo+n3057f52+RvZlf70jix/f8f3YTOdM+Jbdgnvfin67doGFXeAq939qnjnS+GP0hbN+2E3Xcu/c1hsaB1/D6epvd+w/cjnbW1baD5rWenZexu3/fPHPBb6hvtCW1kLrIvsNDbew3zEWKTuWfeal+G643ydxshg/PiU\x17B5\r\n',
            b'\x020zWKLX7Jumz3MQdLziFN2s/yxg2ZfcwYxi+yH9uwcvO5gPGludc/omWsKLoihwOYAWZ0XvtsufvQQY7k6I/5rd9sOczDEHpLZZ41PxX6fKc/5qq8Tl2wbLJZnNtv7+fJtBxgvcLXiPez5X8yBfTjiMNs89Yhv8QGnjTm++TfzHrah9dJdwtlwzJ6xj4KbATY4ms/eIZg6JJijvZuE0wpHVcUeBt8rn+8Y3twuNrqrZSgM7eK+\x17C9\r\n',
            b'\x021NvtE7mvF5xCPHGKcak50dWOnKnzUTArPjlku8t0bxEchhyPKZ/unn/BWk/7sYntnPKF1Kda7jnUb0JvmEOHFL4Qft4hfLP6t/kLa9Bn3C91Kztua6/ER+BxiB73yORjP3BFz4YPRvPW6sfUtzYHIhzbrc3D3ccu5+l5sbQfbscZLRceDL9q3oD9x3U6xI/S0rDlKfhj/8UXrSTraKtjZ2LhHHp2CC+V0fNF+ZHCkORg88gz6\x17B1\r\n',
            b'\x0221pxgPNEvPYvx4HJ+Pv3oga017Cv1rN1jGzumnQea16r9Izvsckv7seqI2PBO8Tvw827hlIKLHrrc020dlHvrYrdDMDC32zH4sn2EfGWR5WA/Y1s2uqrb0VDHVpH5RuEQfAZy2tl2xxwJ2EWe9SnR18bGCzauZ27ieAMOFV63t80hi8Ekc4Lsarvgo/jhBnkeHJ3tGG5fxrrSOKG0Z3hK+GFj+13uqY4xHw2KjGrqWN79RybN\x1782\r\n',
            b'\x023/uHMffNM5Aj/gM3NjdUaPP2b+0jf6C88MjjIzxHfbeV+aI35C7ZlsN+g46wPMY8Al8EFyEDciyz3SV0bGeOS22fDU1uYL8UfX7Tdyu9/Nf71E9anxuQHGmP4WOI/rdPWxqlwslnu+Uz8dbm+Rv5fCHeADcYHGzj2UPtpE9fAa8REm5mfqj2si2pSnrW6fSrPABPwAviSXY5iy5GdbmP/1D8+slzHeCcWQt+Kq3fK9WslLgHb\x1747\r\n',
            b'\x024xcc3RQYVMUK5tnOM5UtbtL5T5Ntvwoc7BV8r2x+Lr9aMrSL38nzikE6JHxVX0cZ1rSPwKn2WdvbBzzctI+qvjjSHIJMe7dl9nB+l+x2NafmnDYyzYZGR8gQ2tOwHB7oP4o5y/fAEy7tJrEOsjy0pjjnC2NX4ZX/bDfhXrLeH41utiSXe1br4V93XwWGR91L2N1oL+5Trq/ZKX3c1f8NzDXbCdYckRkCm+MQD7OPVngPM/3At\x17C0\r\n',
            b'\x025clKM9RX3Q/HtnuZZxcMbm/c1v7mX+wcXD77rz/GT4pRDLMcG/i7xxpBYcMQlW5nDhNEdHUPJt+1m+1F8+Cn7XeRDXEFdmkNBJ7u5j2rrv9kn8zc4oS3DI2yf2Lry+ZYPVvY2LuEgdKVxzC6Ow+TfvhBf/G3rDFwpJ3HEf19P/LGfuVOciV//ugvcLV+Lb9zeXCb7YRywrvFC/4iDxHOlzt5R5nVx90G2C+HqC+Ghg+0HNI+9\x17E8\r\n',
            b'\x026YfS3t3Uj297CHIfNyz9u6r8HxW8zniSmkX1taRxoTfFrjq3hxfqE2BIxKJ8dZp0oZhvzd4pxvuaYZpC1FDCkOAaZj8ZMxBGMCYrOhkc6toBzFft+3njXGOXT1iPcI0xPsByRhXw27dzYnK/51719D5wnXl3GfkA5HjuanzTW28K2LE7fNZxwqGUEnzAeAevSA7r5rnkeLqBvYFfz3ruYqxVX7ho73Cn+ZR/bA59pDvKzweKF\x170D\r\n',
            b'\x027Y4qJtda9g+0BHGrMiS1OsC2BnearlhM+Cb6kbfX3bL8a33/Fz8OXabx2kOWheHL9+Ap0hq7/Xur4cfl7Vnn/bHlGed/5SXk/M+Wlcv8jpfy0tOdPpZTv+yd6LFOXMT1xS+d4286wxOHNuf4cLAwKNvoFD8Py/bDcM7zAY6LeD8r35drBUR43w1edfnktn3dKH6vCv8SlnVJPr8TPjE86xYcPptoWhpeUz0p9FTIr9dTlmhrs\x17D5\r\n',
            b'\x020neN4p1fu79xXynXlntPNIU2JMXs3WFf15FLHReX9UcZ5v9Rd31quv7T8XeqqziqvV4xpHmFwqZ+reOE4t2lQ3leljt61xsPgVF/fKd8z/u/wnCnl+xvL91eVQj+Ps9/oF7n1ioz6V48p7qD9zc1uUzWt1HOB76uucryIP0Yu+BXKsNTTfNf8iA6Qd1Vk0X+g/H2hx3TDyx3XIeNmiv+GrzvUfWapt/SvOtdyolSXlXKp5UBf\x178B\r\n',
            b'\x021B1ea0zpFzvWx0ccPrIte0WXzA+sbDPfPsmwHJ1sHjHc6t5W/+f5g41LPK99rjnZtY7tDvUVmddFDfYH9Mr6mc5T9TqfIp1dk0iCvIot+kXuf5xe/2QcrpZ/9Y42fDv2nP2CiXDMscugd4+9r4pG9fS+8jJ3V4ILPmCcq8ujT7oKdXmkjsWG/tKd/ufXVu9C4Ac910cugPENjzHJ9p7R9iM7KtQPwdIllg+wVc5bvqvPNW4PS\x170B\r\n',
            b'\x0225s6pxpH0RAwMhorcO8FjnTb0r3I/e1f4eX2ec6Px0pR6Bue67b17yr2ML8v1HfQKPwQ7ihl/YC6rj7GNYGNwwXCq/0b3jDuR8xAMl3Z3iu7rc43DAXX+0PoZ3Oq29u41fuEt5I2NURf9GR6VeAAdnB1MFd33ig47Jxgfg4LfYbGbJnOVwl75rgOmShs6RQaDM8wJ2BtjBcUsd9geOzdZ/4xR0T14w+aRS5/5r9KeptTTK7gf\x1773\r\n',
            b'\x023XBKfMilcdIv10TnPdtAHS7e6DjCH3pAdesDG4ak+8QuyOcB2CKYYw4GvwUnGODY5/H7kUK5tSps70+3DGOf1LzYumiLbBlvkOd9yW3ulPw2yQtYrWUfYTO982y9xYv8I430I3/J9wUjvBOMS7gG78qGFE3q3OXbU3MP+sY3Sjrq0oVeeM5xiXPSvczvgD80nlmv78NeBrpv5MPzu8GjbJPFQ/wbbLM+S/1/F/lH2RDuIB4o+\x1724\r\n',
            b'\x024m+utv6Y8s3O27Wl4lv0EPqCJffXghWOtY+rTmOtoy6Jzbfo82TbaJDZgHDC82nzDNVXpb/8af8+z4EzkTlvhDGFrsv3P4Gpji/4NLwue4cjvGYf1JcHA0X4GGEKvxJ6aKzzcupCvYTx3k/UI58Mb9VnGSu/2UrCZC30tz6A94s0zLIt6mu0WPpXOi40PbjJem3JtfXXaAceh37Ptm4Sti2J35Vn9O+J7LnK92Dtzc8Mi+7rU\x172B\r\n',
            b'\x0250znLNj08NzyOPopNa4x2in0mchoc71i5uTuYgKNK/zu3GwPIqjnez8f3EUtQd+908wfcBy+BT+Iw7pVvG4xpjhFdD09yzFQX3updHM6bYo5g3AbnUDdjEGGdmOJu3wcO5Jfxo2CwjAmYw9D8K1i6MpwFFxbcVN91XfBOD15hvF5k1j8mMVzBQ+8u82uvcEB1Y66/zPiADxQT41NWiz89wnrv3BKeOdS4hyOIUfqXWKbIDxwP\x1723\r\n',
            b'\x026TzN+eviHAy1jZN1BX0cmTrrG2K/PcJ3En/WZtpMhY9m9zI3C1VmJh0o7NR9yvl975bnDW83rsk9iqONcZ7/0q4/9nmi7B0f9m2xL4Bu+4nrmqcAXsiKmR698Bo7BLrHnsGBg2Lev6F9mHoQrwSr9xF8IG3eZS3rI6DuJqUs8159uTHSmBUvIq/S/d4rj0Q6Yudtthd/FMxc5JoQL6ivd9+o++1F0Ds65v3O5Y4zB141XzU8f\x1716\r\n',
            b'\x027kTjybOMZO+Mexvey9cvtR4d32c8TH4GTqtjH8Cb7qeFV4aSTzJ+jGLCCx76UeGDfxJmnOTbWHp5+cHdOnjfZ+maOhvEm62E8n5ixCa4ZB/AMOKJ//5jnk3e2nuCQwQPmPfy2fFLBWYeYBV1MtuzREbzLfDT+CDmAOXwitoYfYI69d6z9F3oTd55nPzRE19eYy4gHZPflGcMrHQMSK2Er9XmJIy5y+8GxxrwXxP+A+YPNA7SV\x174E\r\n',
            b'\x020+El2eWvmTyZ7/EV/iKX6yPZC+z3p7AjzC3xCfCkfCcdMs5/TmsXpsf3jjBFeGQv37nQ7B9/P2OJIy1Lx9N6Oh7gW3y3b+J59DjGb4pWjjBfp+HjHysI38RJx3kXWp2z8ROOEeBmZVrfY78pWWJfoO/YQHs6xvVWsR10Xez0n8w2HBSvls/6FkQV4QpbwxcW2S/lCZHGY7R5OG17veAQ9EuPKp6CHkzMeON4xWP+28OcZtm1x\x17FC\r\n',
            b'\x021yiRzIXzRuSo+43DHWsgHGRJvMI5TfHugY2nh/kj3hfgem2VshZ0rfvqO4zTWYIjPkAW2Cs9XF3t8gG6wP/iB2GCQ8Qlxj9ZTmbthDSDfwWfIGGxo3PG18Pnx5uFR7Cg5n5Q2fys+6xTHAYqlr8p80jn2R8yvIzPkgU6wJergefhE4nDNlZ7jOjuTMlY60fEO/gIfy3gJXYIFYmhwBtcTg+A75MeOt10Re6JXzYuwTnWn24X/\x17BC\r\n',
            b'\x022giOxQeIVrR8dFM6ZbJnjL8Bqc77lrPHAWbGLw21njIcYJ3fONWZ4xZ/hV+Xzp8d+jjH2GAfAseBD4xRsAt4p2GL+RPPzR5g3Wa/BphTTn5RYaZrHbKzFgVvNC8HhUz2u1lrLYeYq+IP4qzMaM1xuu8bPYV/EBvA/8Ra+EA5gXUo+/1jLjZiL+EC+en/7LuTQ8Cxs99DEdleZ/+FgZMZYBh+v+fujM+450vMog4vNY/At40Zw\x17A7\r\n',
            b'\x023pTXE69xeYRDMHxQuIU8AvBC7Ed8d4zgF34esiZtpM76c8T68iK0MprjfivFPzrj6bLcJ/4HNMtfEZ2AXfybMwjlTMrY83XaF767JBWONlpwfcupYhyIPmDUC1lXJYSG3hnwiclmyh0pzkFxDbs2yY9prof1yE32t8n3/ves1WXJZmDskl4k5KdYWydFiHEcOFTlA5OSQY8W9POfNrnKzlH/Auvomvn+Un6Q8p192nd9IG7j2\x17FB\r\n',
            b'\x0243WPen8AaKPkNpV2ayybnifypzfxeeYfkAnXdrsE7xpwLzjw2623UR/4R+WDkFC7vviqHbGP7aOU5kaPCuhrrXbSdeVdy5JifXtR9IS9PeUasfZP/w7O59q3s7WT98Sdd30N7P+JXzcevE1mM8qCzx4HcOOVa8Z71CGJZ1qYYU2W/oXJ/yDFiLvMDbodynDcfc24juss+EuUvkpv29siIHFtyo8lLerGr3CXlqTP/uob1r3nN\x17E8\r\n',
            b'\x025jXNP6Yvakzxh1Uvfki+uPXgLpK3ghLWrddIfcqt4HnUjO/JF0Rf5gsw3vtZ1riH3ss75IctVOcHofvm0/8Pum/YIZp1aeZ3oFj3NYzxLLuSULWe9KMdw2PVawPJui/Y2MJdKDvQibov6xLwIOcOndbUeRc5Zc123av7Y9R4+5lDBxW+6ztU+tetc6Bu7Xncgd5t5bDBGXhp5BWCBXMy5g78jyr1XdZ3z+l73UXm9zHmT07qD\x170E\r\n',
            b'\x0267Uo5YieWep8t5aau19CZpwaPF3e95sr6w0Nd7yMmXwz5PtNVO7R2SB75Y12vb5GzyNrXA12vy1/TVT1a9+LvPfyqPNP3mh+qY7pe33mjq7w67UtgHegLXe/DIB8CvXEv6y/3dM17rN2ylke9fyv3Tutq72b1cHn2fV3l2/FK+4Rf1kBYX2cPzBfL+ye74oPqknL977vOm13InKEcAeb64QyuA4OsD2xpnpEeWU9hTRRdsn7G\x1768\r\n',
            b'\x027tWd4j0rzaKmz8Er1h675bmNzinJgWfPALsnlLO3VvDw5Jc91ZX9ah8cWsOF5jblq0673w7zLnKJ1QDDCfiJyn7bOPR1jm3wKdM18BrmPyk89p/Tjtq73kGLnT3fFAco3/LLlqj0a2NzzXXPVI12tj2E/zeVd2TX61Lr1nm5/nXyl5ofd2Ws0yjmbYJxoDYh5fuZd9zLPV0d1veZRbEa8ha7I/5/c9ZxO0WFzddc5TeQ5Ygfr\x17F4\r\n',
            b'\x020GcfizrfMJ8rnvdr2UFHPxuaL2TnAyd8kZ599KeBEaxnzprBmRV9Y0/qsZYa9Kpf1z13hlfu1Pxa5b5Pv7ux6j9wOafOPSzmzXP/z8npr13xDH17pSu7V70p5vZRTSgEbt5Ty6/L9YeUV+/tTKeeVv4sNVieU8lJ5X65vji/l7vL3L8rrT7tqE9/JvgZd2W5zYXl/RynXlvJU+fuoXMcz/+LSTCrlCbeh+VVX+m3+mvbQ5vPL\x1717\r\n',
            b'\x02137SzYLApXCB75l7qebC8P7m8Pl7Kq2nLU+kHdWM/Z6cPRRbYQDW1FO45ze2SXIrOmsf9HPpSXePnw5twX4XMZpRyVilHls/o3wXlPTh4OX3Cpg4v768v5bel/C7Xj2R3TeTN+4Jv8RQyvqGUK8s193YdT0y1/KqLSjkpz0YPxAsFxw0ccL9l2NCmwn/4sOa8tOvevP7eNi6Zlb4210ZvA/9dlTZWpW/N7aX8IvWdW14nWf+0\x1719\r\n',
            b'\x022SW3jHvjv5vL+nlw7tF7BevMnY6opem/Q/13WqXRyV3QHpqZEZsj30PL+WLeveiw4uj06fibtRu7lmXBBxfP7pYCFS90PtWW6bVG4PK6Ub5S/p+aacn31V+utedVYkuyKrCr44jrLu3kumHvadQiDN0but1qOzenl/f7WX/P9yPHMtHHfUrYu77GzL5fyr6Xs11W8y/hPOaBwMOuyR2cu74seMyhXCR+ym8ctmov+qtc5lG/H\x178F\r\n',
            b'\x023vNq3fD++TzkkR2V8eqTrrkZr9odl/HPhmMenyZNVngC5gfjiz5t3lRuHH9sz7/mu5+u0Np6cD+UDsHa7p5/BOrPuYU0WTmIt+F/Svz3iu8hX/ZJ5m7UJYgby1pQz+rn0gzyG/dw3uK1irogc3vuLDP5Y+jCrlJml/H3Ma6s/G7NNX2SdwDHYQPOIsdNc0RX3V2DkhWARfF9qDsc/YJ9wlrgQe5oWez/HOJfdYpt3h7fOtr1h\x17B5\r\n',
            b'\x024v2BU/uCxXHO5MdIUH15d77/x58Jaqbe6Ls8Ey1ekDeD/Udu0Ymbq+Un6cm1sHA44IjZ6lbkC30WfZPsPpG3g9azwS7GJ6lTbA5/LLig/iP0VmTC+gX/gOtV7R+zp6Njw6ZHBj8prua/5WVcxnZ71k/DMFb63eSj9w9bPTf9vT5vPC3edn/Zin/D4C7HxmyM7+vlsrrnG16E79ev+POdq2xS8Ix6m3aeP61zcUGQqLr8qev1p\x17C0\r\n',
            b'\x025MDLD/ZdcL7fO8NsVdRef0JxgLOizp8Jtz6T98QviXnwXvH1x5AHPnBFZYe/EwU9aR5IB/cXnPmJ+aS4r7++MjO7I85/IZ3DohamL7y6LfEZ6pu7Tgnd0+3K4qfhQ+QJ8RsGo/N3Nac8DwVPRo/wicp0cPrwzzwHnLwcDV/oatfUat6cZyfH71rnaWrANd0v290TvU/P+L2kf9nJL7Kr0RT4BvUyxbcmfPxTdBIt8J7u82XKn\x17F4\r\n',
            b'\x026L+Lii+foxw3BywX+HL6W3M6xfmVH91s24FI+fWSLl6Ytp0U/x+WZt1ju4our84w7/Kr70cHUyIYY4gDjQDaDPm6LTd+Quqb7c/nei9PfGyxL5K9rbo6cb4yMfhh7u8d6VLzBtfihP0f+Rc5NwbPi29ujT/R+UnRF34nlkAU6KfGEfOSTwS02dmKe0Y8MnnLbaYMw+ds58HFv7P8u6wq/Cc80I869Ju15Oni4K59dkO/vie6w\x17C8\r\n',
            b'\x027H+IP/OPRtk1xxiD2g0+9Jc/9jfEuXN6c/tGGGdHVtOgcWT0RGdwRXF1h+1Yc9nBs+5TUc136MSN9vjZ9vCk6eD36IJb6SZ7xYDA9iN55FjHZecHfLZHz3dHp+fnsCbdFvHVm+o+s/xz9320dUYfiEGLFi41h4fjp6OF+61r1nhrcgqe7045L3FZsUjyMTm9M3++yDUg/j7hduv6B1IGMbnPfxQ1Xxk6wd3AC/6BnuHpa9F7q\x1753\r\n',
            b'\x02019k1L0TPM4Jz+nxlrhkYm9LtQ3nej4xv/JKed2XaDF7hvUvTz8fSnwu6s7lCPg37uSq44/Xx4O2iyPH53H9T+vRc8D6K+x6xPQkjF+e+26K3c/Md902ynuRXfp/+3Zhrwcsd1pXs6XbjVOMreIaxxt8i2wfG8cHn4hZs93TLVZi5Of0Aa9dHPnflHq4/MPgBu8fHlm4O/n+W9l7ke6WTR4MPriNenmKMS4e3BI/EAPcGGw8F\x171C\r\n',
            b'\x021iz9Im982Jh+n/mFPTfT5VDD848h0euqYEltCt5dFz+dHV4/4Gv0NV50dfLzk98LWs7HVR9K28gz2BGs8gF0wNrzXtiD7n5T+D2KjN9heNWaBB+6LXh60/ctvnxm7nZF2THEbZuNkRtqF3f8i+gELyJc5o5Pd5+ZB40sx1ow8L+Na6fmc4PG6tBFdEnc8E/uYmufflvZNC86uM76Jq+RjuT9xBNjVGJK+PBxZ0e+X8ty73WfZ\x17AC\r\n',
            b'\x0227RXp485dnemg6y61rch+Lgh2ZwRr4O8O40Dxxb3p9/To9VpjTH1O/KTnXW+7lw+5w/0Sjq5P+/GHl6aOG3LPw6mL93Dds8ZbNfINo/hnSsoZsdvzUtdojHirMQJHSc4PB4c3ReY/S59vCp7Pj7zvsI2q3J5rL3P92sMOHl8Lph5ze+QPkPc2sXEw9Hj6hCzgm2O69s2/iJwGsednLXfGBtIb/PNobOrqYOxh27uuvyxtw1Z/\x1732\r\n',
            b'\x023lL69bPkoBiDWvys4RM6nRi4jzmU8H85U3P8741YcS90nxWZuDNZmxY5HmL8tdvNU9EosdXjwO9X9l399KP2/3G1tRj734tg/sfBtvk72caF1Jhkhwz8H89OC6/gLtemnsYvB+DPEHdTbBFfXW0fC0dnR4+mRy73Wu2RybfjiBstXXETMy9iGeQw4+tXombH7U5av5g3A34tpe+YgFJMhg3PT5jetT+ZkNZdzcbBzp+1K/H1R\x1788\r\n',
            b'\x024rgV7YGV69Hhn2o188Cu/cX+E5Te6jrWmmQNU74XhFvR9VF6npn2UW3L/SFfnu11aA+D7P9jmFA//MHJ+IHaHbBPXysfFtuVn6Ad+GVlOdntkf9cZX4orqPNF64L5dsn/3tgL+sOXJu6qDnF/JU/mWCYZa7JleP3Irv3+2b5HfmyqsS47mBzc3R183W68aszA5ydHRw/aBoTpxLeaPwM/VwV7PPevwQr4nB4sPx4Z8ez7bAOS\x17EC\r\n',
            b'\x0259aXuE2ttshO4ijmiV7rmz7Ntv2rnfZEttjXF7RBGJxvX4l0wcETwxufnWO86I2daZMM9fzI+ZNe0aWh70XzGbeGJe2Nz59kOqp5lr77Sf3A1I9ddZbyID2knPuMK91v6+XnwgX45pwE8YHs/jSyfdb3i2+npyyD28XS+K9yt+bNH0o4bgrHzI1uwPMMyV//uM+7E4092x+PBW2Jj+E+499fGpjj+PGNfdV7hZ6rv1Htyd/Y4\x17DD\r\n',
            b'\x026bfYYg3HkM2n3s6mHtpyYa3+evp0VmwRjX85zwO9jlou49hTrTbjBx18SPXLf8cHiXXmdnnppB5g4K+2+NTJlLggZ/iK2eJevwT+wRijuYB73oXBB4ls9F54iJjw2956U/l8cmbFGeWtsdlqwfkkwep6vU71XR+Y3pv7RfMuFkccVsTH6Rt8vyv3o57vhCbjvfvdNnP1w8PpI+spzGFsRpz1v+UsP0y0rxZcPBgdvGzNOkc+N\x177C\r\n',
            b'\x027uZ/4+J/BxXXuu/p3TXfc/z8TXT+Xtl8ZPP3dOlJ/kcHMtPeo2PVVscufdcfn8OCCu40D4RgMv5D+IPu3u43EWZoPu9r3Kka5NO8H4QXs7tXgaBS3/sA6E/7gxONs48LJy8H9JMtEfT/NMhS/ph3i0Z/b9sWd6Ck8Ic4pbdB5Z/i3xyL78reweWts5oVg5zG/1zhqsm1CsvqRsSMM35vPkcFo/uje7vgc6SWx52mWn8ZO1H1l\x1757\r\n',
            b'\x0202gX/hrM1n5mxpGzvltjFo7Fp9Eh88Mu04YrYGPp/wByge++PvVzvditWR2a/NZ71zDNsT+K2ybG3x2I/D6YvXHdqbA55Mhf4hDGk2AK9zIpebsu9B0cXz0Vm4HJ65EA/r40dvxCMH24si++mW0eys2muQ59dFiyBnVGsQ733+XPFM8SWT7pvxFuy/+etY+HuorQ37ZH8kM+p+ey14Iq+42s5/5I2Px2dnJPno6fRXOwLkTs6\x1797\r\n',
            b'\x021ujnYwd/9qDub0yR3dE0b4PjE39wnOznPfdeYEM74SXCKjO9Kmxn7gZ1wrOp5zdgHd6wRaf6ctj4UDEwJDs6wvcnO0cdJtl/h+5zY9bWR8c3RzYWRGViZEb0/6Ff5m+tiKzel/zf72fLN09KGq2yj8gNwwz1+la7R2ZOWq/p5XvrJPNirsf0/WmbCO7J+PjLlmd+KbaCThyPnvm1d/f1VdDgtcrh+vI2sh+p846np22tp4w2R\x1778\r\n',
            b'\x022wVvRM3wxmntODKgxSHy0bOBYfy+eRafkL+BHnuiOz/+h19EcU9/tFsff7Gc3I39/h7EoHvyLdSI+J2acEj2HmxV/T40snrOsFeedE5u4Ifp42bJV/063ztQ35PhL24RiqKnd2T5Hcdpky0F/T7WsZs/voN8/G+eSF3gdzZPgk891m2XnT6ZPtOeNyAN/mVijGa2t3BW7vz1yGs3l3JA2TI8Mr7btKR4dtZPcDfJlDnXODHkD\x1764\r\n',
            b'\x0235PNpbzx5JduMzT77V7kB7JPlzIBdnIOg8yMmJJfsO84F0rn/mzq/SXt9t3aOYTU635UcoG97jZA9IuR66SyuXZxvQj6G9oKzZ/XDyTXh/Nd9nXOi89a/6JxHnQ1Njhr7LCf4Ou3P4gyy3bznTmfSrODnK29pHa8x6nyafdw/cizIeyDvt8n+be3nXsL5dewtYO+Bzuuey31mLZG81SZ5pKxTsqdO5wuVdulMWdqPjMjZIfd7\x17CF\r\n',
            b'\x024MbeFvCnyNcmz5CxRncu0q/PT6py/pH2vY84R016aYy0DnTVCzsXF7rtyS8krYb8KMtrba6E6d/H9zuNi7ZVcbHKGtcecvNnPpH768s3kHK3m3Bfl3y+XXD1kQK7nTu4LOZ7K0Tsq+c7bWVbKRdsv+wgWzV64HxgL0it7osnZIvd0exdkRk61zqQk54ec+tJWndHPmXi0ifywy7w2TK6V1qqLfDlbh5xc/YYC+TWXOL+JnGbt\x170F\r\n',
            b'\x025ywenqzoPkP1Udc6/1D7uzbNXLnvx0Av5VNozvaafzdq48t2+5vV1rY+zTr2cr2XNm/zR/mTn42mP415un7BPTh02cUNyBddJ7gyyI5+MPMTSV3JXyTkjr71/adasj0nu4QTnFrEvgPVwPWOL5DMtkr0NxyWX6YC0/dPpx67WD/u7h+wBYX/ZAc7BYq+c9pud7T4p523ZMeU5aX/IclnDb7J/jpxCziojf45z2dZKLhl5T+Sr\x17D4\r\n',
            b'\x026sfd9W9uC8lipkxzP5Y0HnYPBful9nPPG+UucpaEc/O9ZLsrT/aZz7XV2wGG+tnOHZU7OOP0jp17nisAxc6XP5OBht+RSftL4gx+0Z4fchYnON2CPGmdVYD/Kc7rEe+CUF0reG3kHH4/NruGcO/WD/GTywsAj9kDuGec3wGPrOaeBnD9kT74FMtfeh0nZY7tX9nMcY94UX7LfjPOfyLf+oG2AfXjISedOjs4ZI/+L88rncS45\x17BE\r\n',
            b'\x027udXs59E+vB2c+wZXVzlvh3OndFYMe9rnNY50hgm5khe6Tdo3Pzp/bFvvP9B5peSuI7tv+j72bwmb6Jv9xd+2nnUGytLmbuW7rmN5qN4t3X70yl4k5SuSi7JQ+LS2jrXP98DkcqCjeZ23rxzHhc21OvN0L+/BIp9Pv63C+SXk7F9uf8R5RuTu6/w+9ip825zK/mz6od++WNu60llJeya/Dc463rZOe8RFh7udcK729ODjDopf\x17A0\r\n',
            b'\x020hOtPMefqLAty8b9nu4O7wIz2JR5hW9IZXMv5ucoXhmOQ7bbmA+WMfsM5Lux7wp9o7+b27of4m3MUDjQfaq/s2eYwfAB74HR+zem2dfZBad/HV4OXI6wn9j3o7LQlbPc6H2F386pws7+fgY7FF3D2hfaR7IHQ72ZsFjlwXs3Xnacvv4LOkf8+3menM4o/Hfv7Xjh3uXD4FpY5+wTYG6Azk4IlfBf5/k1+Q0bxwFcsG54JRyqP\x177D\r\n',
            b'\x021B97NWUvssxCXYE+reZ+NzgzCtyMTYhp4d6FgDnmsb7+p/PlNrX94RWc0kXdMfPBN789osv9Wfmnj8OvFjnnISW1G+8YWtU/UOaQXeJ+FuLDgmn1y7Mvj2dpT/2X7Hu0HZz86uVHbmEORAXt9dLbRosavzs2Cpw7OHnPisK7rZ89EnbPtdM4T7SOHkzxY8qRWsc9Wbuo3LBdx7cKOV3RO5z7Wb0Vbj41PgCs2Mb8ol3vhyJ2z\x17AC\r\n',
            b'\x022UBewf2Vvis5k3Cf3Ibv3xfYutR3L1jh/9TOWqc5q2Tj7ydayb9A5QKvGVj7tGEg+bxHbqX5Lg3ww+H3d+JGNvLdD++rJ0Z7P8tGZvuTJbun4RuedHuS26TzY7RL/IJOvG9v0W+e8wP/k/nPOIecc7WG5y/ctbg4mxiQOlC9kryr7pDfP3q2D3T7y9pUrTr4Z+fDso5vqfSM6n+eY4PqEcC251GvYz9Y520dny4CRnKEt/zKv\x1728\r\n',
            b'\x023uVZxcO39buyHU0y2jHEj3O+U69fyPlX2z+ssO2y2SWzGWR2T3V72aZIrJz0f4r3LOi9qmez9usn36czk7bOH8wjbuHwMZxCuY7vB3yofcB/LVPuiNjfns5ePWErniixhH8h+G8Xm6ybenCdtWdH70LSPY5nonTz57YJp8Mw5P0eaC1Xnlyxf4f7rxp3OlvuW+ZGcQfSkvSD7GXP4EfpA23VuBfutPxc5EiNz7i77d3b23+y1\x1707\r\n',
            b'\x0241b6jfR336TcD4DKwe6xtgbMmVM+y1rPyL4mRGcuA1T3cv4p95bs73pCsvmu/pzPb+furjon02zy1YwLOF2CPoM784NwY+JixGWctse9ouWAGf7u04wGdxfF+t1mxODHB17IXcyP7CvZ4yea+aRnqDAXq+ZTjOOV6w1VH287Yq6nfiVrYuNE5+J+IHCY675RYf/Z+z03CVSvZV+isuFNs/4rLGfecbHvQuckfihwudt+Jj8QX\x178A\r\n',
            b'\x025h47N/k0pbE/nD17jdoIB5bATN+4VG0K24Ii9u0caG3CQ9uCzv5EzufayX9a5Q5wFdJrtS7+lsZX7w7O1J+5g2za5taoPX8O+5O2cU6vf0cg5+OSmaqywmfuis67nsr0zvtYZfOv7GdIz9xxqzMOj2juFD/ioMaRz/ibajw8SL8iPg8Mp7hd4J9Yid5YzMrTPY63gEv9FjMG4kfEC3M84dJL7zRl6OquE2Ghfy4+9g/rNzmXs\x1716\r\n',
            b'\x026P7Vv8npzgX5jCjs50T5MObmMjRfKHtzD7JN1Bmr2N+ss/wMsL40F2POMfL9muRIP6jeCtrI/0NmKPJ8Y9okxnY3E75n2KTPL9fmbV2Jsxk76rHxXzcw1pTSlaK/fjHLdX5zvy/cDXl8rpdRdc07RK6VwttJvyt+Plfv+6fuHT5drS73VU/67/mX57KXy/cPls5+Vv2nD78vzXvH31D943rnF1ZPl/Z/chvpHrofv+w+7nfWo\x175F\r\n',
            b'\x027P79KP27zNYNH/XddPu8My/fP+lrOguq/6rbX6duwtKfzx9TFnuvfuM764fH8ZupSH3h9rtxzc7k3n6n9M90eyYoc6Jf9veT4vJ+FrPm+91fLdpj2dP5W7nmxfP6U5dH7c3l9sHz22Lgu6rfcR+Vaz3JR/3/utqpuPp8+/qzq9Xz2k3LNi+O67g39/M6b5bOnIovS194/LNfBm+N903lad6S9Rc+dfx/Hz2wMUOcD5ftnogPO\x17A5\r\n',
            b'\x020hil+r/czf1elrdIp+7LR++/K6zOWnXT6e9dX/bb8XTDW/H0cf/Xj5bNf+rmD8vnwD+X6X/q76g33rVPuq4rc+qU/nV+PPxc8Iqv+z91+YeP5cZxRJ9cPg/fqpeiy4Ef7eWeO63+Egf6oT4+Udt43blOdu8vff47cwMLfrJ8RNqp7Ip/8PUw9I5sbYZkc+k5wxfkJuv+5OdrysHHEvTqrg9diJ33sKnLrj7D+Y9tlNfD9vdKm\x1739\r\n',
            b'\x021KljgvuZV16/n/nm8HYORXrCzB1wXHNJ5odxf5NUr+O685DpH1/beiD2VOpsXglW49ffp/+/9PX3rFWx2CncMweZD4YSRnH7te5s3wyX3RF8P5f7y3P5fgocR/sAs7XndfeuMdPwf5fNf+f3gP2M3TwT//7TsR7bYi10N5njfi3xGXNkv2BtGp4NhZE9b77XOO8GR6rllHIfNiDvA9kV+Bjge0Iais94M3y87/l1wzzWvpx3h\x177E\r\n',
            b'\x022jsHtsVf+Lu2ornF76lJPffu43gdF5/3Yf38wjl+4EFtpiq0Pfm2dDdHLM263zjGb6e+lyyJHxprNs25f72nHDHVkX4crsNvOnHj+z2A0PNsZ6anwbFP63S/81rw1jkNxyovG9vBF+xvq47n9WeNl5JcGBV/N626DcPMH67fOc0Y2qOtfyufg6bfBbZFJ/btxPTcjmyp97RS+qV5wHc3LsfvX4z/S7w4881b4nPt+nut43l/n\x172D\r\n',
            b'\x023sImR/kf2Gl/RnznOJbSt9yPLqJ41Bw5Seq/lmtzT+2W4ijb+Lu3/U9o7J3bRI7Icybxwd/0H+6Y5fdowGK6nz8HHr+S7q+NPfhOb5P2f5rgu8ud9fWn6RF03/8/9Hfmd+oXx2IMzw9g31JmDQ+RTCiZ7jweHhVM5+6ca2Sl1vxyMU094poEniRNuj93Piq5TbxOZDufgcvFE4fAOe5lmeH6R+mQL08flX/8p9vfceD3N79P3\x17B5\r\n',
            b'\x024uyxPeL6a0/bejM5fsU9R/7Cpp+fgjF/Fpu533NF5Mn732bR5pFuuKfY9fHmONs2yjwLz2Hk/8hgUPfWKzQ5fCLdN8/WyqRmxsRcdm1Vwz29skyPs9X47HnMMi756b9nH9n4RHbxuLI1kORzEz/wwch350egUOfWHkXVpq87fmTnOifhzMCl9zRiPiUac0Dwam6Lu/wy+iTH/EX/1F/s49evfExv9LZh8Nn661N88ELudZV/Z\x17BA\r\n',
            b'\x025zNHGeuT/Zo5js3rV/IjuhveER14wH0kP5XOdMVie1bxhngDbNe25Z9xW8RF6Zvm+X9o/KL6nN4pNg81+kXn9wBx2OOLMWeN9px7Zxaxx+SGPqmCoSUyuv0e2zTVTzXH9grnqH/Z7wtvPx2Oy/qzxOIQzUnsjuT89LgtiT9nUc8E382y/GY9vRzzQeTU6/3XaXOKYYdEJ56QQu464jvEC8X8Vfm0KvzUFX4MSZw7fTNw203Hn\x1720\r\n',
            b'\x0264PXx50geb1mGzbTESEVuVeFD8uL0m0fk9JBjSW7D3GP+TS5yklg3J/+6vNe54lzD3tR3j/ksDQrj5nu7+s0k/d5f+U6/Q8v6+Bqpi7yBn3Z9liO5HYwxmbdkbm89f09+us5ueNm5PpprXSz1LT6mPEv9Th9jSNawWBf5j+7sszV0RsbC/oy8WP1+7Dxus3KGchaI9qIzX/RMV3vLNef/wTHnbRQ56HfK/+DfmdNvl3PGyMxu\x177B\r\n',
            b'\x0271ePsJ84gIQeL+Q9yCEpbdXYEa8fsw39XnsFvcv04Mv1VV3N5+m29N7o6N0K/N0+OFrnN/+zOPvdDOUzkQdCXInP93hVrBv9Mvia/c0l/X3I+gnIX5sqzyXEkF5h14g9ZjsqbIDf0la5+K005SCumz7SVfN33pd3vH9NvUen37fNeOVbLjnmu9sWuf2Mu+tHvrvE387Gcp8BaMM/gdy4XTPvfaflrvRMZPRJ5LTlm2eQcCq13\x1775\r\n',
            b'\x020gcNFjSX9FtGCxo5+Q5X5Gc6YYe6Qa5hbX8Ay1e82ISMKe4wWs3z0+6H0nxy58rfOfwC7zI9ylglzcvQNzH02uCG3hLlc5qE552TpsfF8syec56LfZH/GONG8+FvOy9DvOn7A+GJ/m3S3gtuu3yHN79Bpvgzds3f7desGvKIn5Rat6r7qPBzw+1rXa1JLWDc644J9Z8wt/yF5RvMZ++BLeUzkgVSWn3IPyWcCczN9vX4bDRt+\x1739\r\n',
            b'\x0213LLWGT77uD9a+2INGPy8lv6iO3IeWHPHZsE+eYN/97kX6EDzTKzJwhtv5nnYyjujt/fZnnTGOG1mj/Djtnny63QuDXOGrL8vZm4gn0tnU1TmJv3233tin+9P/U91nZsxwc+mXp25AtbA7+c8D6gzxVkPYE6NOUzO9ObcN+ZQWYfhTDnmPA/0/Cxzbzqfm/nBvcZ0BhXrzZwjxrmqrGlzDgZzsprPhB8O9RwY6y+c3ao6OJuV\x1700\r\n',
            b'\x022OeKNM4d5ptcitEbBXC3nbTHnyH2sz5zodQ7N8RYs6XcheAbzyswJMp9MPgNrQJz3dv6Y59P4nTPOmWNe9V88b6bzIjnLjN9jYc2NNXHmwg50uzVPz9wefLiV5xNZo2GeX2cflzZxfhVzxsiJM8E4Y17nv+7r57NOW4/WRJhfZU69yFxrcMhvG2OZPBSt/zP/xroUaxH0mTVCZFSew/qXzpvdYcxnFHJu91meJ+csQc41VO4A\x17C3\r\n',
            b'\x023ayTlvXJ5eCZrdAUPnOumtcp13S7NEXK2L2umnLFVMMU5Wswb6wy27xj7yn041nImF0TnrHJmXt94Z86eNTed9cJ6EjKmbtYpT/Fzm+Rr6OzdI71WpPXjuVw/Z7/BA5w1p3UC1jM4Jw0OQe/HWSZaOy5yY91XZ0XST9afdrQ+tabKvDVrFpwDVjhM53gvENmypnOw+63fjmZdF5/Tj5w5W4d54lIv88Xyb8zTs65U8Dt4KNeX\x173B\r\n',
            b'\x024OELn4cIPu435vM3EWqyN6Bxnzti6xvyruGJ3xxoam0xJHHZu+prYSb+jt2DGMayhlBim/qnjJHDLnCZrr4oDWQ9gbf8jGVf91m2QLyjPqbmHOdsSX7JGRN91FgTzvP/hOIe5XeY9dO78LPsOjUVY1yeeGMWcf/X3+h25axL33uX4m3Ux4mPmGkdjM+ywJs5infWNjKcmjM2ezxjFhL2ptmOtPzP3zvogNlviGNb1iLPrjI8G\x175E\r\n',
            b'\x025zOfRtqUypsVHbeJ2MW+h31T+p2NixhPIR3NYjOHfCA5+EVllPMC8xeBJ40xziHBHfrupLmMe5lYYjyhXbpbngFjXBUP9fziO1ZoscvqxuQZbZi2esxr1u5dftI7JY6v/aJmKi17GR5nnemXMqDPX/zI+54EOdUYia0CP4mvHNG8NlwxfGx/XsO6js6wZ06+W8dkSHmNyHjDxoHS3SOY1Z5kfNIaYHv9InF3GPsxZc4an4tk3\x174F\r\n',
            b'\x026I/sfZuz0kOMt4YH8DNbwii12mG9f0bLRWuj8GVdzviH4LePV4ZMZmxxnLhGPrJc5nC09b6zxDflB5xj/TWxcv7lFLk8ZQ+vczpMzvhjOMa6ZaS7QnNVuGdftaz7EvzUZ57O+xnmDGnuTm0n+OXmfv0ru543O6VRe7U+Tu3nmeE6qckPxzwd1fd7G+S46syh7N5SfW3yrzvHKPkjVd61zeZVrTE4sOdFnO47Q91x/TXJwyY8d\x17BA\r\n',
            b'\x0277b04uus9Y5xj9BnnvirvlZzh6/Jc2kbe+RFdnVegXF5i4EMd52oPwozUc5DfK5+2m3xZ2jE6U4A29xLTkddMfvoJaceZflVOLbnIeyd/987080eJSV7JvcT5+3TH92cylmIsQdzzUGKxlyw3xW3k+7MniZxq3hPDsa+BmOr13EteMXv7Pt91DjH5v8juEucGN6MzrF5InHWM26q9xeRhb9L1PgNk+Gh0iKwmpY2f63r/C3nj\x17A0\r\n',
            b'\x020Z3THzy0hb/ecjEnI/SVnnz18h+f5r+TaCx13zd6ru7vbXeWsKe0NmeS+SofkKZPX3/dzlT/O/j/qyNkv1Shf+sDu7DNTFL89lOdtEfldah1KZ4wv0CHxYcGUcvJ5/o5pM3vz2AcwOfXea30pd5nc+JOi8xu6s/fKaFx0SNd7KCbFVrKfSGMp8H9RsH5LMAy+hrXP3QGn53Zn75sSBu6M/s80rtUm9DDDdUtO06KnJjbyZGR6\x170E\r\n',
            b'\x021fPSKTG+Ofun78bEp9HqPbUb6Zu/NabYbtRFMPRHcop8S17NvQvE/8mZvCzj+dXREWx+LnJAveyrQD7oIPyAj/fbxvZHBH3yNcsN/Fp55IjqkLsZ62Bxy/m144Pnu7H0mGl8Vvem3lAq3shbMuJYxmn4rvsTO5b+2tKUtbWlLW9rSlra0pS1taUtb2tKWtrSlLW1pS1va0pa2tKUtbWlLW9rSlra0pS1taUtb2tKWtrSlLW1p\x1728\r\n',
            b'\x022S1va0pa2tKUtbWlLW9rSlra0pS1taUtb2tKWtrSlLW1pS1va0pb/WqX91/5r/7X/2n/tv/Zf+6/91/5r/7X/2n/tv/Zf+6/91/5r/7X/2n/tv/Zf+6/91/77b/uvbktb2tKWtrSlLW1pS1va0pa2tKUtbfmvUZr/g1K3pS1taUtb2tKWtrSlLW1py3/B8v96z2Nb2tKWtvzfLNtv0pa2tOV/t9RtaUtb/r8og7otbWnL/82y\x172B\r\n',
            b'\x0236ib/69Kv/2uU3ib/fcqwtHfuTf7nUqn8Dw==\r\x0343\r\n',
            b'\x024M|4|REAGENT|CLEANER\\DILUENT\\LYSE|221114I1*^20230307000000^20230607\\221031H1*^20230307000000^20230907\\221026M11^20230307000000^20230507\r\x03F3\r\n',
            b'\x025R|1|^^^NEU#^751-8|2.03|10E3/uL|1.60 - 7.00^REFERENCE_RANGE|N||W||NNEMT^^USER|20230324134947||\r\x03C3\r\n',
            b'\x026R|2|^^^MCV^787-2|82.0|um3|76.0 - 100.0^REFERENCE_RANGE|N||F||NNEMT^^USER|20230324134947||\r\x0313\r\n',
            b'\x027R|3|^^^NEU%^770-8|28.8|%|40.0 - 73.0^REFERENCE_RANGE|L||W||NNEMT^^USER|20230324134947||\r\x0331\r\n',
            b'\x020R|4|^^^RDW-CV^788-0|11.9|%|11.0 - 17.0^REFERENCE_RANGE|N||F||NNEMT^^USER|20230324134947||\r\x03B8\r\n',
            b'\x021R|5|^^^MPV^32623-1|8.6|um3|8.0 - 11.0^REFERENCE_RANGE|N||F||NNEMT^^USER|20230324134947||\r\x03E7\r\n',
            b'\x022R|6|^^^RBC^789-8|5.19|10E6/uL|3.80 - 6.00^REFERENCE_RANGE|N||F||NNEMT^^USER|20230324134947||\r\x039B\r\n',
            b'\x023R|7|^^^MON#^742-7|0.50|10E3/uL|0.20 - 0.80^REFERENCE_RANGE|N||W||NNEMT^^USER|20230324134947||\r\x03C4\r\n',
            b'\x024R|8|^^^WBC^6690-2|7.06|10E3/uL|3.50 - 10.00^REFERENCE_RANGE|N||W||NNEMT^^USER|20230324134947||\r\x03FF\r\n',
            b'\x025R|9|^^^PLT^777-3|269|10E3/uL|150 - 400^REFERENCE_RANGE|N||F||NNEMT^^USER|20230324134947||\r\x0320\r\n',
            b'\x026R|10|^^^MON%^5905-5|7.1|%|4.0 - 12.0^REFERENCE_RANGE|N||W||NNEMT^^USER|20230324134947||\r\x0323\r\n',
            b'\x027R|11|^^^LYM#^731-0|3.14|10E3/uL|1.00 - 3.00^REFERENCE_RANGE|H||W||NNEMT^^USER|20230324134947||\r\x03E9\r\n',
            b'\x020R|12|^^^HGB^718-7|14.3|g/dL|11.5 - 17.0^REFERENCE_RANGE|N||F||NNEMT^^USER|20230324134947||\r\x0328\r\n',
            b'\x021R|13|^^^LYM%^736-9|44.7|%|15.0 - 45.0^REFERENCE_RANGE|N||W||NNEMT^^USER|20230324134947||\r\x0369\r\n',
            b'\x022R|14|^^^BAS%^706-2|1.0|%|0.0 - 1.2^REFERENCE_RANGE|N||W||NNEMT^^USER|20230324134947||\r\x039B\r\n',
            b'\x023R|15|^^^BAS#^704-7|0.07|10E3/uL|0.00 - 0.20^REFERENCE_RANGE|N||W||NNEMT^^USER|20230324134947||\r\x03D7\r\n',
            b'\x024R|16|^^^MCH^785-6|27.5|pg|27.0 - 34.0^REFERENCE_RANGE|N||F||NNEMT^^USER|20230324134947||\r\x03D2\r\n',
            b'\x025R|17|^^^MCHC^786-4|33.6|g/dL|32.0 - 35.0^REFERENCE_RANGE|N||F||NNEMT^^USER|20230324134947||\r\x0380\r\n',
            b'\x026R|18|^^^HCT^4544-3|42.5|%|35.0 - 52.0^REFERENCE_RANGE|N||F||NNEMT^^USER|20230324134947||\r\x0351\r\n',
            b'\x027R|19|^^^EOS#^711-2|1.29|10E3/uL|0.00 - 0.50^REFERENCE_RANGE|H||W||NNEMT^^USER|20230324134947||\r\x03EB\r\n',
            b'\x020R|20|^^^EOS%^713-8|18.4|%|0.5 - 4.0^REFERENCE_RANGE|H||W||NNEMT^^USER|20230324134947||\r\x03E7\r\n',
            b'\x021L|1|N\r\x0304\r\n',
        ]

        # Mock transport and protocol objects
        self.transport = self.get_mock_transport()
        self.protocol.transport = self.transport
        self.mapping = horiba_yumizen_h5xx.get_mapping()

    def get_mock_transport(self, ip="127.0.0.1", port=12345):
        transport = MagicMock()
        transport.get_extra_info = Mock(return_value=(ip, port))
        transport.write = MagicMock()
        return transport

    def test_communication(self):
        """Test common instrument communication """

        # Establish the connection to build setup the environment
        self.protocol.connection_made(self.transport)

        # Send ENQ
        self.protocol.data_received(ENQ)

        for line in self.lines:
            self.protocol.data_received(line)
            # We expect an ACK as response
            self.transport.write.assert_called_with(ACK)

    def test_decode_messages(self):
        self.test_communication()

        data = {}
        keys = []

        for line in self.protocol.messages:
            records = codec.decode(line)

            self.assertTrue(isinstance(records, list), True)
            self.assertTrue(len(records) > 0, True)

            record = records[0]
            rtype = record[0]
            wrapper = self.mapping[rtype](*record)
            data[rtype] = wrapper.to_dict()
            keys.append(rtype)

        for key in keys:
            self.assertTrue(key in data)

    def test_h5xx_wrapper(self):
        """Test the message wrapper
        """
        self.test_communication()

        wrapper = Wrapper(self.protocol.messages)
        data = wrapper.to_dict()
        results = data.get("R")
        result = results[0]
